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
from google.cloud.firestore import FieldFilter  # 🟢 NEW: Firestore Error Fix
from binance.client import Client  
from pybit.unified_trading import HTTP  

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
    # 🟢 REMOVED: waiting_for_sender State রিমুভ করা হয়েছে
    waiting_for_trxid = State()          
    waiting_for_crypto_trxid = State()   
    waiting_for_screenshot = State()     
    payment_method = None  
    method_key = None      
    method_type = None     

# ==========================================
# 🏦 DIRECT DEPOSIT MENU (Dynamic from Database)
# ==========================================
@router.callback_query(F.data == "menu_wallet")
async def show_deposit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    
    methods = await get_all_payment_methods()
    crypto_buttons = []
    local_buttons = []
    
    for key, data in methods.items():
        if data.get("is_active", True):
            btn = InlineKeyboardButton(text=data["name"], callback_data=f"dep_{data['type']}_{key}", style="primary", icon_custom_emoji_id=EMOJI_MONEY)
            if data['type'] == 'crypto':
                crypto_buttons.append(btn)
            else:
                local_buttons.append(btn)
                
    keyboard_layout = []
    for i in range(0, len(crypto_buttons), 2):
        keyboard_layout.append(crypto_buttons[i:i+2])
    for i in range(0, len(local_buttons), 2):
        keyboard_layout.append(local_buttons[i:i+2])
        
    keyboard_layout.append([InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")])
    text = "🏦 <b>Deposit Funds</b>\n\nChoose your preferred payment method below:"
    
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
    
    if m_type == "crypto":
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="crypto")
        await state.set_state(DepositState.waiting_for_crypto_trxid)
        
        if m_key == "binance":
            pay_id = method_info.get("pay_id", "Unknown")
            instruction = (f"⚡ <b>{method_name} (Auto Verification)</b>\n\n🔹 <b>Pay ID / UID:</b> <code>{pay_id}</code>\n\n⚠️ <i>Please send USDT to the Pay ID above. After sending, type your <b>Order ID or Transaction ID (TrxID)</b> below:</i>")
        elif m_key == "bybit":
            pay_id = method_info.get("pay_id", "Unknown")
            instruction = (f"⚡ <b>{method_name} (Auto Verification)</b>\n\n🔹 <b>UID:</b> <code>{pay_id}</code>\n\n⚠️ <i>Please send USDT via <b>'Withdraw -> Internal Transfer'</b> to the UID above. After sending, type your <b>Transaction ID (txID)</b> below:</i>")
        elif m_key == "bybitaddress":
            address = method_info.get("address", "Unknown")
            instruction = (f"⚡ <b>{method_name} (Auto Verification)</b>\n\n🔹 <b>Supported Networks:</b> BEP20 (BSC)\n🔹 <b>Deposit Address:</b> <code>{address}</code>\n\n⚠️ <i>Please send USDT to the address above. Wait 1-2 minutes for network confirmation, then type your <b>Transaction Hash (TxID)</b> below:</i>")
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")
        
    else:
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="local")
        await state.set_state(DepositState.waiting_for_amount)
        
        instruction = (f"📱 <b>{method_name} (Auto Verification)</b>\n\n🔹 <b>Minimum Deposit:</b> 20 BDT\n\n⚠️ <b>How much money do you want to deposit?</b>\n<i>(Type the amount in BDT below. Example: 100)</i>")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# ⚡ CRYPTO API VERIFICATION LOGIC
# ==========================================
def verify_crypto_pay(trx_id: str, platform: str):
    if platform == "binance":
        if not BINANCE_API_KEY or not BINANCE_SECRET_KEY: return {"status": "error", "message": "Binance API keys not set."}
        try:
            cache_ref = db.collection('settings').document('binance_cache')
            cache_doc = cache_ref.get()
            current_time, needs_update, cached_data = time.time(), True, []
            
            if cache_doc.exists:
                c_data = cache_doc.to_dict()
                last_update, is_locked, cached_data = c_data.get('last_update', 0), c_data.get('is_locked', False), c_data.get('data', [])
                if current_time - last_update < 60 or (is_locked and current_time - last_update < 120): needs_update = False

            if needs_update:
                cache_ref.set({'is_locked': True, 'last_update': current_time, 'data': cached_data}, merge=True)
                try:
                    client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
                    history = client.get_pay_trade_history(limit=100)
                    if history.get('code') == '000000' and 'data' in history: cached_data = history['data']
                    cache_ref.set({'is_locked': False, 'last_update': time.time(), 'data': cached_data})
                except Exception as e:
                    cache_ref.set({'is_locked': False, 'last_update': time.time(), 'data': cached_data})
                    raise e

            for tx in cached_data:
                if tx.get('orderId') == trx_id or tx.get('transactionId') == trx_id:
                    amount = sum([float(f['amount']) for f in tx['fundsDetail']]) if tx.get('fundsDetail') else float(tx.get('amount', 0))
                    return {"status": "success", "amount": amount, "currency": tx.get('currency', 'USDT')}
            return {"status": "failed", "message": "Transaction not found. Please wait 1-2 minutes and try again."}
        except Exception as e:
            if "Way too much request weight" in str(e) or "-1003" in str(e): return {"status": "failed", "message": "Binance server is busy."}
            return {"status": "error", "message": str(e)}

    elif platform in ["bybit", "bybitaddress"]:
        if not BYBIT_API_KEY or not BYBIT_SECRET_KEY: return {"status": "error", "message": "Bybit API keys not set."}
        try:
            session = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_SECRET_KEY)
            internal_res = session.get_internal_deposit_records(limit=50)
            if internal_res.get('retCode') == 0 and 'result' in internal_res and 'rows' in internal_res['result']:
                for tx in internal_res['result']['rows']:
                    if tx.get('txID') == trx_id:
                        if tx.get('status') == 2: return {"status": "success", "amount": float(tx.get('amount', 0)), "currency": tx.get('coin', 'USDT')}
                        else: return {"status": "failed", "message": "Transaction is still Processing."}
            deposit_res = session.get_deposit_records(limit=50)
            if deposit_res.get('retCode') == 0 and 'result' in deposit_res and 'rows' in deposit_res['result']:
                for tx in deposit_res['result']['rows']:
                    if tx.get('txID') == trx_id:
                        if tx.get('status') == 3: return {"status": "success", "amount": float(tx.get('amount', 0)), "currency": tx.get('coin', 'USDT')}
                        else: return {"status": "failed", "message": "Network Transaction is not confirmed yet."}
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
            if trx_ref.get().exists:
                return await processing_msg.edit_text("❌ <b>Fraud Alert:</b> This Transaction ID has already been used!", parse_mode="HTML")
            
            trx_ref.set({'user_id': user_id, 'amount': amount_usd, 'currency': currency, 'platform': method_key, 'timestamp': firestore.SERVER_TIMESTAMP})
            await save_deposit_history(user_id=user_id, amount=amount_usd, method=platform_name, trx_id=trx_id, currency=currency)
            db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
        
        success_text = (f"🎉 <b>{platform_name} Verified!</b>\n\n🧾 <b>TrxID:</b> <code>{trx_id}</code>\n💰 <b>Amount:</b> {amount_usd} {currency}\n\n<i>Your balance has been updated automatically.</i>")
        await processing_msg.edit_text(success_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Go to Shop", callback_data="menu_buy", style="success", icon_custom_emoji_id=EMOJI_CART)]]), parse_mode="HTML")
        await state.clear()
        
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, f"⚡ <b>AUTO DEPOSIT SUCCESS (CRYPTO)</b>\n👤 User ID: <code>{user_id}</code>\n💰 Amount: {amount_usd} {currency}\n🏦 Method: {platform_name}\n🧾 TrxID: <code>{trx_id}</code>", parse_mode="HTML")
            except: pass
    else:
        fail_text = f"❌ <b>Verification Failed!</b>\n\n⚠️ {result.get('message', 'Transaction not found.')}\n\nPlease check your TrxID and try again."
        await processing_msg.edit_text(fail_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="menu_wallet", style="danger")]]), parse_mode="HTML")
        await state.clear()

# ==========================================
# 📱 LOCAL PAYMENT FLOW (AUTO-RETRY + SCREENSHOT FALLBACK)
# ==========================================
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit(): return await message.answer("⚠️ Please enter a valid number:")
    amount = float(message.text)
    if amount < 20: return await message.answer("⚠️ <b>Minimum deposit amount is 20 BDT.</b>\n\nPlease enter an amount of 20 or more:", parse_mode="HTML")
        
    await state.update_data(deposit_amount=amount)
    
    # 🟢 NEW: সরাসরি TrxID চাইবে, Sender Number স্কিপ করা হলো!
    await state.set_state(DepositState.waiting_for_trxid) 
    
    data = await state.get_data()
    methods = await get_all_payment_methods()
    admin_receiving_number = methods.get(data.get("method_key", "bkash"), {}).get("number", "Unknown")
    
    instruction = (f"📱 <b>Payment Instructions</b>\n\n🔹 <b>Method:</b> {data.get('payment_method')}\n🔹 <b>Amount to send:</b> {data.get('deposit_amount')} BDT\n🔹 <b>Send To:</b> <code>{admin_receiving_number}</code>\n\n⚠️ <i>After sending money, type your <b>Transaction ID (TrxID)</b> below:</i>")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
    await message.answer(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext, bot: Bot):
    trxid = message.text.strip()
    user_id = message.from_user.id
    processing_msg = await message.answer("⏳ <b>Processing your request...</b>\nPlease wait a moment.", parse_mode="HTML")
    
    if len(trxid) < 6 or not trxid.isalnum():
        return await processing_msg.edit_text("⚠️ <b>Invalid TrxID Format!</b>\nPlease provide a valid alphanumeric Transaction ID.", parse_mode="HTML")
    
    if db:
        existing_deposits = db.collection('pending_deposits').where(filter=FieldFilter('trx_id', '==', trxid)).limit(1).stream()
        for _ in existing_deposits:
            return await processing_msg.edit_text("❌ <b>Alert:</b> This Transaction ID has already been submitted in our system!\n\n<i>If you think this is a mistake, please contact support.</i>", parse_mode="HTML")
            
        if db.collection('used_trx').document(trxid).get().exists:
            return await processing_msg.edit_text("❌ <b>Fraud Alert:</b> This Transaction ID has already been used!", parse_mode="HTML")

    user_data = await state.get_data()
    method_name, method_key = user_data.get("payment_method"), user_data.get("method_key", "bkash")
    expected_amount = user_data.get("deposit_amount", 0.0) 
    
    is_auto_verified = False
    actual_amount = 0.0 # 🟢 NEW: ডাটাবেস থেকে আসল অ্যামাউন্ট নেওয়ার জন্য
    
    # 🟢 1ST ATTEMPT: Instant Check (ইউজারের অ্যামাউন্ট ইগনোর করে আসল অ্যামাউন্ট নেবে)
    if db:
        sms_doc = db.collection('live_sms_payments').document(trxid).get()
        if sms_doc.exists and not sms_doc.to_dict().get('is_used', False):
            is_auto_verified = True
            actual_amount = float(sms_doc.to_dict().get('amount', 0.0))

    # 🟢 2ND ATTEMPT: 1 Minute Wait
    if not is_auto_verified:
        await processing_msg.edit_text("⏳ <b>Checking Server...</b>\n<i>Network delay detected. Please wait 1 minute for auto-verification...</i>", parse_mode="HTML")
        await asyncio.sleep(60)
        
        if db:
            sms_doc = db.collection('live_sms_payments').document(trxid).get()
            if sms_doc.exists and not sms_doc.to_dict().get('is_used', False):
                is_auto_verified = True
                actual_amount = float(sms_doc.to_dict().get('amount', 0.0))

    if is_auto_verified:
        amount_usd = round(actual_amount / 125.0, 2)
        db.collection('live_sms_payments').document(trxid).update({'is_used': True, 'claimed_by': user_id})
        db.collection('used_trx').document(trxid).set({'user_id': user_id, 'amount': actual_amount, 'platform': method_key, 'timestamp': firestore.SERVER_TIMESTAMP})
        await save_deposit_history(user_id=user_id, amount=actual_amount, method=method_name, trx_id=trxid, currency="BDT")
        db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
        
        # 🟢 মেসেজে আসল অ্যামাউন্ট শো করানো হচ্ছে
        success_text = (f"🎉 <b>{method_name} Verified Successfully!</b>\n\n🧾 <b>TrxID:</b> <code>{trxid}</code>\n💰 <b>Received:</b> {actual_amount} BDT\n💎 <b>Added:</b> ${amount_usd}\n\n<i>Your balance has been updated instantly.</i>")
        
        if actual_amount != expected_amount:
            success_text += f"\n\n⚠️ <i>Note: You claimed {expected_amount} BDT, but we received {actual_amount} BDT. Your balance is updated with the actual received amount.</i>"
            
        await processing_msg.edit_text(success_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Go to Shop", callback_data="menu_buy", style="success", icon_custom_emoji_id=EMOJI_CART)]]), parse_mode="HTML")
        
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, f"⚡ <b>AUTO DEPOSIT SUCCESS (LOCAL)</b>\n👤 User ID: <code>{user_id}</code>\n💰 Amount: {actual_amount} BDT\n🏦 Via: {method_name}\n🧾 TrxID: <code>{trxid}</code>", parse_mode="HTML")
            except: pass
        await state.clear()
        return

    # 🟠 FALLBACK: ASK FOR SCREENSHOT
    await state.update_data(fallback_trxid=trxid)
    await state.set_state(DepositState.waiting_for_screenshot)
    
    fallback_text = (
        "⚠️ <b>Transaction Not Found Automatically!</b>\n\n"
        "Due to network issues, SMS delay, or incorrect TrxID, we couldn't verify your payment instantly.\n\n"
        "📸 <b>Please send a SCREENSHOT of your payment receipt now.</b>\n"
        "<i>(Our system will send it to the admin for manual review)</i>"
    )
    await processing_msg.edit_text(fallback_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]]), parse_mode="HTML")

# ==========================================
# 📸 PROCESS SCREENSHOT FOR MANUAL REVIEW
# ==========================================
@router.message(DepositState.waiting_for_screenshot, F.photo | F.document)
async def receive_screenshot(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    
    method_name, trxid = data.get("payment_method"), data.get("fallback_trxid")
    expected_amount = data.get("deposit_amount", 0.0)
    
    # Extract highest quality photo
    photo_id = message.photo[-1].file_id if message.photo else message.document.file_id
    
    # 🟢 NEW: sender_number হিসেবে "N/A" পাঠানো হচ্ছে
    deposit_id = await create_pending_deposit(user_id=user_id, amount=expected_amount, method=method_name, sender_number="N/A", trx_id=trxid)

    admin_text = (
        "💰 <b>NEW DEPOSIT REQUEST! (Manual Fallback)</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"💵 <b>Claimed Amount:</b> {expected_amount} BDT\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
        "📸 <i>Review the screenshot below.</i>"
    )
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Verify Now", callback_data=f"viewdep_{deposit_id}", style="success", icon_custom_emoji_id=EMOJI_DONE)]])
    
    for admin_id in ADMIN_IDS:
        try: await bot.send_photo(chat_id=admin_id, photo=photo_id, caption=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
        except: pass

    pending_text = (
        "✅ <b>Screenshot Received!</b>\n\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
        "👨‍💻 <i>Due to a server error, your transaction has been sent to the admin for manual review. Your balance will be added once approved.</i>"
    )
    await message.answer(pending_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main", style="primary")]]), parse_mode="HTML")
    await state.clear()
