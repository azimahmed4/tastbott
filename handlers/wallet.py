# ==========================================
# File: handlers/wallet.py
# Purpose: ডিরেক্ট ডিপোজিট সিস্টেম (Binance/Bybit API Auto Verify এবং Local Payment)
# ==========================================
import os
import time  
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore
from binance.client import Client  
from pybit.unified_trading import HTTP  # 🚀 Bybit API লাইব্রেরি

# 🟢 NEW: get_all_payment_methods ইমপোর্ট করা হলো
from database.crud import db, create_pending_deposit, save_deposit_history, get_all_payment_methods
from config import ADMIN_IDS

router = Router()

# ==========================================
# 🎨 PREMIUM EMOJI IDs 
# ==========================================
EMOJI_MONEY = "5368324170671202288"
EMOJI_CART = "5368324170671202286"
EMOJI_DONE = "5368324170671202287"

# ==========================================
# ⚙️ API KEYS CONFIGURATION
# ==========================================
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")
BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY")
BYBIT_SECRET_KEY = os.environ.get("BYBIT_SECRET_KEY")

if BINANCE_API_KEY and BINANCE_SECRET_KEY:
    masked_key = BINANCE_API_KEY[:5] + "********"
    print(f"✅ [SUCCESS] Binance API Keys loaded! (Key: {masked_key})")
else:
    print("⚠️ [WARNING] Binance API Keys MISSING! Auto-Verify won't work.")

if BYBIT_API_KEY and BYBIT_SECRET_KEY:
    masked_key = BYBIT_API_KEY[:5] + "********"
    print(f"✅ [SUCCESS] Bybit API Keys loaded! (Key: {masked_key})")
else:
    print("⚠️ [WARNING] Bybit API Keys MISSING! Auto-Verify won't work.")

# ==========================================
# 📌 States
# ==========================================
class DepositState(StatesGroup):
    waiting_for_amount = State()         
    waiting_for_sender = State()
    waiting_for_trxid = State()          # Local-এর জন্য
    waiting_for_crypto_trxid = State()   # 🚀 Crypto-এর জন্য
    payment_method = None  
    method_key = None      
    method_type = None     

# ==========================================
# 🏦 DIRECT DEPOSIT MENU (Dynamic from Database)
# ==========================================
@router.callback_query(F.data == "menu_wallet")
async def show_deposit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    
    # 🟢 ফায়ারবেস থেকে লাইভ পেমেন্ট মেথডগুলো আনা হচ্ছে
    methods = await get_all_payment_methods()
    
    crypto_buttons = []
    local_buttons = []
    
    # যে মেথডগুলো ON (is_active = True) আছে, শুধু সেগুলোই বাটনে অ্যাড হবে
    for key, data in methods.items():
        if data.get("is_active", True):
            btn = InlineKeyboardButton(text=data["name"], callback_data=f"dep_{data['type']}_{key}", style="primary", icon_custom_emoji_id=EMOJI_MONEY)
            if data['type'] == 'crypto':
                crypto_buttons.append(btn)
            else:
                local_buttons.append(btn)
                
    keyboard_layout = []
    
    # বাটনগুলো দুই কলামে সাজানো
    for i in range(0, len(crypto_buttons), 2):
        keyboard_layout.append(crypto_buttons[i:i+2])
        
    for i in range(0, len(local_buttons), 2):
        keyboard_layout.append(local_buttons[i:i+2])
        
    keyboard_layout.append([InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")])
    
    text = "🏦 <b>Deposit Funds</b>\n\nChoose your preferred payment method below:"
    
    # যদি কোনো পেমেন্ট মেথড ON না থাকে
    if not crypto_buttons and not local_buttons:
        text = "🏦 <b>Deposit Funds</b>\n\n⚠️ Deposit system is currently disabled by the admin."
        keyboard_layout = [[InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]]
        
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_layout), parse_mode="HTML")

# ==========================================
# 🔄 PAYMENT METHOD SELECTION PROCESS
# ==========================================
@router.callback_query(F.data.startswith("dep_"))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    m_type = parts[1] 
    m_key = parts[2]  
    
    methods = await get_all_payment_methods()
    method_info = methods.get(m_key)
    
    if not method_info or not method_info.get("is_active", True):
        return await callback.answer("❌ This payment method is currently disabled.", show_alert=True)
        
    method_name = method_info.get("name", "Payment")
    
    # 🚀 Crypto Flow
    if m_type == "crypto":
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="crypto")
        await state.set_state(DepositState.waiting_for_crypto_trxid)
        
        if m_key == "binance":
            pay_id = method_info.get("pay_id", "Unknown")
            instruction = (
                f"⚡ <b>{method_name} (Auto Verification)</b>\n\n"
                f"🔹 <b>Pay ID / UID:</b> <code>{pay_id}</code>\n\n"
                f"⚠️ <i>Please send USDT to the Pay ID above. After sending, type your <b>Order ID or Transaction ID (TrxID)</b> below:</i>"
            )
        elif m_key == "bybit":
            pay_id = method_info.get("pay_id", "Unknown")
            instruction = (
                f"⚡ <b>{method_name} (Auto Verification)</b>\n\n"
                f"🔹 <b>UID:</b> <code>{pay_id}</code>\n\n"
                f"⚠️ <i>Please send USDT via <b>'Withdraw -> Internal Transfer'</b> to the UID above. After sending, type your <b>Transaction ID (txID)</b> below:</i>"
            )
        elif m_key == "bybitaddress":
            address = method_info.get("address", "Unknown")
            instruction = (
                f"⚡ <b>{method_name} (Auto Verification)</b>\n\n"
                f"🔹 <b>Supported Networks:</b> BEP20 (BSC)\n"
                f"🔹 <b>Deposit Address:</b> <code>{address}</code>\n\n"
                f"⚠️ <i>Please send USDT to the address above. Wait 1-2 minutes for network confirmation, then type your <b>Transaction Hash (TxID)</b> below:</i>"
            )
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")
        
    # 🚀 Local Flow
    else:
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="local")
        await state.set_state(DepositState.waiting_for_amount)
        
        instruction = (
            f"📱 <b>{method_name} (Auto Verification)</b>\n\n"
            "🔹 <b>Minimum Deposit:</b> 20 BDT\n\n"
            "⚠️ <b>How much money do you want to deposit?</b>\n"
            "<i>(Type the amount in BDT below. Example: 100)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# ⚡ CRYPTO API VERIFICATION LOGIC (WITH FIRESTORE GLOBAL LOCK)
# ==========================================
def verify_crypto_pay(trx_id: str, platform: str):
    if platform == "binance":
        if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
            return {"status": "error", "message": "Binance API keys not set."}
        try:
            cache_ref = db.collection('settings').document('binance_cache')
            cache_doc = cache_ref.get()
            
            current_time = time.time()
            needs_update = True
            cached_data = []
            
            if cache_doc.exists:
                c_data = cache_doc.to_dict()
                last_update = c_data.get('last_update', 0)
                is_locked = c_data.get('is_locked', False)
                cached_data = c_data.get('data', [])
                
                if current_time - last_update < 60:
                    needs_update = False
                elif is_locked and current_time - last_update < 120:
                    needs_update = False

            if needs_update:
                cache_ref.set({'is_locked': True, 'last_update': current_time, 'data': cached_data}, merge=True)
                
                try:
                    client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
                    history = client.get_pay_trade_history(limit=100)
                    if history.get('code') == '000000' and 'data' in history:
                        cached_data = history['data']
                    cache_ref.set({'is_locked': False, 'last_update': time.time(), 'data': cached_data})
                except Exception as e:
                    cache_ref.set({'is_locked': False, 'last_update': time.time(), 'data': cached_data})
                    raise e

            for tx in cached_data:
                if tx.get('orderId') == trx_id or tx.get('transactionId') == trx_id:
                    if tx.get('fundsDetail'):
                        amount = sum([float(f['amount']) for f in tx['fundsDetail']])
                    else:
                        amount = float(tx.get('amount', 0))
                    return {"status": "success", "amount": amount, "currency": tx.get('currency', 'USDT')}
            
            return {"status": "failed", "message": "Transaction not found. Please wait 1-2 minutes and try again."}
            
        except Exception as e:
            if "Way too much request weight" in str(e) or "-1003" in str(e):
                return {"status": "failed", "message": "Binance server is currently busy. Please wait 1-2 minutes and try again."}
            return {"status": "error", "message": str(e)}

    elif platform in ["bybit", "bybitaddress"]:
        if not BYBIT_API_KEY or not BYBIT_SECRET_KEY:
            return {"status": "error", "message": "Bybit API keys not set."}
        try:
            session = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_SECRET_KEY)
            
            internal_res = session.get_internal_deposit_records(limit=50)
            if internal_res.get('retCode') == 0 and 'result' in internal_res and 'rows' in internal_res['result']:
                for tx in internal_res['result']['rows']:
                    if tx.get('txID') == trx_id:
                        if tx.get('status') == 2:
                            amount = float(tx.get('amount', 0))
                            return {"status": "success", "amount": amount, "currency": tx.get('coin', 'USDT')}
                        else:
                            return {"status": "failed", "message": "Transaction is still Processing. Try again later."}
            
            deposit_res = session.get_deposit_records(limit=50)
            if deposit_res.get('retCode') == 0 and 'result' in deposit_res and 'rows' in deposit_res['result']:
                for tx in deposit_res['result']['rows']:
                    if tx.get('txID') == trx_id:
                        if tx.get('status') == 3:
                            amount = float(tx.get('amount', 0))
                            return {"status": "success", "amount": amount, "currency": tx.get('coin', 'USDT')}
                        else:
                            return {"status": "failed", "message": "Network Transaction is not confirmed yet."}
                            
            return {"status": "failed", "message": "Transaction not found on network."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@router.message(DepositState.waiting_for_crypto_trxid)
async def process_crypto_trxid(message: Message, state: FSMContext, bot: Bot):
    trx_id = message.text.strip()
    user_id = message.from_user.id
    
    data = await state.get_data()
    method_key = data.get("method_key") 
    platform_name = data.get("payment_method")
    
    processing_msg = await message.answer(f"⏳ <b>Communicating with Blockchain Server...</b>\nPlease wait a few seconds.", parse_mode="HTML")
    
    result = await asyncio.to_thread(verify_crypto_pay, trx_id, method_key)
    
    if result["status"] == "success":
        amount_usd = result["amount"]
        currency = result.get("currency", "USDT")
        
        if db:
            trx_ref = db.collection('used_trx').document(trx_id)
            doc = trx_ref.get()
            
            if doc.exists:
                await processing_msg.edit_text("❌ <b>Fraud Alert:</b> This Transaction ID has already been used!", parse_mode="HTML")
                return
            
            trx_ref.set({'user_id': user_id, 'amount': amount_usd, 'currency': currency, 'platform': method_key, 'timestamp': firestore.SERVER_TIMESTAMP})
            await save_deposit_history(user_id=user_id, amount=amount_usd, method=platform_name, trx_id=trx_id, currency=currency)
            db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
        
        success_text = (
            f"🎉 <b>{platform_name} Verified!</b>\n\n"
            f"🧾 <b>TrxID:</b> <code>{trx_id}</code>\n"
            f"💰 <b>Amount:</b> {amount_usd} {currency}\n\n"
            f"<i>Your balance has been updated automatically.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Go to Shop", callback_data="menu_buy", style="success", icon_custom_emoji_id=EMOJI_CART)]])
        await processing_msg.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        
        # 🟢 Admin Notification for Auto Crypto Deposit
        admin_text = (
            f"⚡ <b>AUTO DEPOSIT SUCCESS (CRYPTO)</b>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💰 Amount: {amount_usd} {currency}\n"
            f"🏦 Method: {platform_name}\n"
            f"🧾 TrxID: <code>{trx_id}</code>"
        )
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except: pass
        
    else:
        error_msg = result.get('message', 'Transaction not found.')
        fail_text = f"❌ <b>Verification Failed!</b>\n\n⚠️ {error_msg}\n\nPlease check your TrxID and try again."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="menu_wallet", style="danger")]])
        await processing_msg.edit_text(fail_text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()

# ==========================================
# 📱 LOCAL PAYMENT FLOW (SEAMLESS HYBRID SYSTEM)
# ==========================================
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit():
        return await message.answer("⚠️ Please enter a valid number:")
        
    amount = float(message.text)
    
    if amount < 20:
        return await message.answer("⚠️ <b>Minimum deposit amount is 20 BDT.</b>\n\nPlease enter an amount of 20 or more:", parse_mode="HTML")
        
    await state.update_data(deposit_amount=amount)
    await state.set_state(DepositState.waiting_for_sender) 
    
    data = await state.get_data()
    method_name = data.get("payment_method", "Payment")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
    await message.answer(f"📱 <b>Which account will you Send from?</b>\n<i>(Type your 11-digit {method_name} number below)</i>", reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_sender)
async def receive_sender(message: Message, state: FSMContext):
    sender_num = message.text.strip()
    
    if not sender_num.isdigit() or len(sender_num) != 11:
        return await message.answer("⚠️ <b>Invalid Number!</b>\n\nPlease enter exactly 11 digits for your sender number (e.g., 01311111111):", parse_mode="HTML")
        
    await state.update_data(sender_number=sender_num)
    await state.set_state(DepositState.waiting_for_trxid) 
    
    data = await state.get_data()
    amount = data.get("deposit_amount")
    method_name = data.get("payment_method", "Payment")
    method_key = data.get("method_key", "bkash")
    
    methods = await get_all_payment_methods()
    admin_receiving_number = methods.get(method_key, {}).get("number", "Unknown")
    currency = "BDT"
    
    instruction = (
        "📱 <b>Payment Instructions</b>\n\n"
        f"🔹 <b>Method:</b> {method_name}\n"
        f"🔹 <b>Amount to send:</b> {amount} {currency}\n"
        f"🔹 <b>Send To:</b> <code>{admin_receiving_number}</code>\n\n"
        "⚠️ <i>After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
    await message.answer(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext, bot: Bot):
    trxid = message.text.strip()
    user_id = message.from_user.id
    
    processing_msg = await message.answer("⏳ <b>Processing your request...</b>\nPlease wait a moment.", parse_mode="HTML")
    
    if db:
        # Fraud Checks
        existing_deposits = db.collection('pending_deposits').where('trx_id', '==', trxid).limit(1).stream()
        for _ in existing_deposits:
            await processing_msg.edit_text("❌ <b>Alert:</b> This Transaction ID has already been submitted in our system!\n\n<i>If you think this is a mistake, please contact support.</i>", parse_mode="HTML")
            return 
            
        used_trx_doc = db.collection('used_trx').document(trxid).get()
        if used_trx_doc.exists:
            await processing_msg.edit_text("❌ <b>Fraud Alert:</b> This Transaction ID has already been used!", parse_mode="HTML")
            return

    user_data = await state.get_data()
    
    method_name = user_data.get("payment_method", "Payment")
    method_key = user_data.get("method_key", "bkash")
    expected_amount = user_data.get("deposit_amount", 0.0) 
    sender_number = user_data.get("sender_number", "Unknown")
    currency = "BDT"
    
    # ====================================================
    # 🟢 SEAMLESS HYBRID LOGIC (TRY AUTO-VERIFY FIRST)
    # ====================================================
    is_auto_verified = False
    
    if db:
        sms_doc_ref = db.collection('live_sms_payments').document(trxid)
        sms_doc = sms_doc_ref.get()
        
        if sms_doc.exists:
            sms_data = sms_doc.to_dict()
            actual_amount = float(sms_data.get('amount', 0.0))
            is_used = sms_data.get('is_used', False)
            
            # Auto Verify Condition Met
            if not is_used and actual_amount >= expected_amount:
                amount_usd = round(actual_amount / 125.0, 2)
                
                # Update DB for auto-verify success
                sms_doc_ref.update({'is_used': True, 'claimed_by': user_id})
                db.collection('used_trx').document(trxid).set({'user_id': user_id, 'amount': actual_amount, 'platform': method_key, 'timestamp': firestore.SERVER_TIMESTAMP})
                await save_deposit_history(user_id=user_id, amount=actual_amount, method=method_name, trx_id=trxid, currency="BDT")
                db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
                
                is_auto_verified = True
                
                # Success Notification for User
                success_text = (
                    f"🎉 <b>{method_name} Payment Verified Successfully!</b>\n\n"
                    f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n"
                    f"💰 <b>Amount Received:</b> {actual_amount} BDT\n"
                    f"💎 <b>Added to Wallet:</b> ${amount_usd}\n\n"
                    f"<i>Your balance has been updated instantly.</i>"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Go to Shop", callback_data="menu_buy", style="success", icon_custom_emoji_id=EMOJI_CART)]])
                await processing_msg.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
                
                # 🟢 Admin Notification for Auto Local Deposit
                admin_text = (
                    f"⚡ <b>AUTO DEPOSIT SUCCESS (LOCAL)</b>\n"
                    f"👤 User ID: <code>{user_id}</code>\n"
                    f"💰 Amount: {actual_amount} BDT\n"
                    f"🏦 Via: {method_name}\n"
                    f"🧾 TrxID: <code>{trxid}</code>"
                )
                for admin_id in ADMIN_IDS:
                    try: await bot.send_message(admin_id, admin_text, parse_mode="HTML")
                    except: pass

    await state.clear()
    
    # ====================================================
    # 🟠 FALLBACK TO MANUAL VERIFICATION (IF AUTO FAILS/NOT FOUND)
    # ====================================================
    if not is_auto_verified:
        deposit_id = await create_pending_deposit(
            user_id=user_id, amount=expected_amount, method=method_name, sender_number=sender_number, trx_id=trxid
        )

        # Admin gets Manual Approval Request
        admin_text = (
            "💰 <b>NEW DEPOSIT REQUEST! (Manual)</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"📱 <b>Sender:</b> <code>{sender_number}</code>\n"
            f"💵 <b>Amount:</b> {expected_amount} {currency}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Verify Now", callback_data=f"viewdep_{deposit_id}", style="success", icon_custom_emoji_id=EMOJI_DONE)]
        ])
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
            except Exception:
                pass

        # User sees standard pending message silently (no failure notice)
        pending_text = (
            "⏳ <b>Deposit Request Submitted!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"💵 <b>Amount:</b> {expected_amount} {currency}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
            "👨‍💻 <i>Your transaction has been securely sent to the admin. Your account will be updated once approved.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main", style="primary")]])
        await processing_msg.edit_text(pending_text, reply_markup=keyboard, parse_mode="HTML")
