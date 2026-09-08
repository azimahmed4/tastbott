# ==========================================
# File: handlers/wallet.py
# Purpose: ডিরেক্ট ডিপোজিট সিস্টেম (Binance/Bybit API Auto Verify এবং Local Payment)
# ==========================================
import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore
from binance.client import Client  
from pybit.unified_trading import HTTP  # 🚀 Bybit API লাইব্রেরি

from database.crud import db, create_pending_deposit, save_deposit_history
from config import ADMIN_IDS

router = Router()

# ==========================================
# 🎨 PREMIUM EMOJI IDs 
# ==========================================
EMOJI_MONEY = "5368324170671202288"
EMOJI_CART = "5368324170671202286"
EMOJI_DONE = "5368324170671202287"

# ==========================================
# ⚙️ API KEYS & METHODS CONFIGURATION
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

CRYPTO_METHODS = {
    "binance": {"name": "Binance Pay", "pay_id": "1126025983"},
    "bybit": {"name": "Bybit Internal Transfer", "pay_id": "127145762"},
    "bybitaddress": {"name": "USDT (BEP20)", "address": "0x822ee632c8223cb5b0457e6a8a36221bbe52a87c"} 
}

LOCAL_METHODS = {
    "bkash": {"name": "bKash", "number": "01308618044"},
    "nagad": {"name": "Nagad", "number": "01308618044"},
    "rocket": {"name": "Rocket", "number": "01308618044"}
}

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
# 🏦 DIRECT DEPOSIT MENU 
# ==========================================
@router.callback_query(F.data == "menu_wallet")
async def show_deposit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    keyboard = [
        [
            InlineKeyboardButton(text=CRYPTO_METHODS["binance"]["name"], callback_data="dep_crypto_binance", style="primary", icon_custom_emoji_id=EMOJI_MONEY),
            InlineKeyboardButton(text=CRYPTO_METHODS["bybit"]["name"], callback_data="dep_crypto_bybit", style="primary", icon_custom_emoji_id=EMOJI_MONEY)
        ],
        [
            InlineKeyboardButton(text=CRYPTO_METHODS["bybitaddress"]["name"], callback_data="dep_crypto_bybitaddress", style="primary", icon_custom_emoji_id=EMOJI_MONEY)
        ],
        [
            InlineKeyboardButton(text=LOCAL_METHODS["bkash"]["name"], callback_data="dep_local_bkash", style="primary"),
            InlineKeyboardButton(text=LOCAL_METHODS["nagad"]["name"], callback_data="dep_local_nagad", style="primary")
        ],
        [
            InlineKeyboardButton(text=LOCAL_METHODS["rocket"]["name"], callback_data="dep_local_rocket", style="primary")
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
    ]
    
    text = "🏦 <b>Deposit Funds</b>\n\nChoose your preferred payment method below:"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# ==========================================
# 🔄 PAYMENT METHOD SELECTION PROCESS
# ==========================================
@router.callback_query(F.data.startswith("dep_"))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    m_type = parts[1] 
    m_key = parts[2]  
    
    # 🚀 Crypto Flow (Binance, Bybit & Address)
    if m_type == "crypto":
        method_info = CRYPTO_METHODS.get(m_key, {})
        method_name = method_info.get("name", "Crypto Payment")
        
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
        method_info = LOCAL_METHODS.get(m_key, {})
        method_name = method_info.get("name", "Local Payment")
        
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="local")
        await state.set_state(DepositState.waiting_for_amount)
        
        instruction = (
            f"📱 <b>{method_name} (Manual Verification)</b>\n\n"
            "🔹 <b>Minimum Deposit:</b> 20 BDT\n\n"
            "⚠️ <b>How much money do you want to deposit?</b>\n"
            "<i>(Type the amount in BDT below. Example: 100)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# ⚡ CRYPTO API VERIFICATION LOGIC
# ==========================================
def verify_crypto_pay(trx_id: str, platform: str):
    if platform == "binance":
        if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
            return {"status": "error", "message": "Binance API keys not set."}
        try:
            client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
            history = client.get_pay_trade_history(limit=100)
            if history.get('code') == '000000' and 'data' in history:
                for tx in history['data']:
                    if tx.get('orderId') == trx_id or tx.get('transactionId') == trx_id:
                        if tx.get('fundsDetail'):
                            amount = sum([float(f['amount']) for f in tx['fundsDetail']])
                        else:
                            amount = float(tx.get('amount', 0))
                        return {"status": "success", "amount": amount, "currency": tx.get('currency', 'USDT')}
            return {"status": "failed", "message": "Transaction not found."}
        except Exception as e:
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
async def process_crypto_trxid(message: Message, state: FSMContext):
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
        
    else:
        error_msg = result.get('message', 'Transaction not found.')
        fail_text = f"❌ <b>Verification Failed!</b>\n\n⚠️ {error_msg}\n\nPlease check your TrxID and try again."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="menu_wallet", style="danger")]])
        await processing_msg.edit_text(fail_text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()

# ==========================================
# 📱 LOCAL PAYMENT FLOW
# ==========================================
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit():
        return await message.answer("⚠️ Please enter a valid number:")
        
    await state.update_data(deposit_amount=float(message.text))
    await state.set_state(DepositState.waiting_for_sender) 
    
    data = await state.get_data()
    method_name = data.get("payment_method", "Payment")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet", style="danger")]])
    await message.answer(f"📱 <b>Which account will you Send from?</b>\n<i>(Type your {method_name} number below)</i>", reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_sender)
async def receive_sender(message: Message, state: FSMContext):
    await state.update_data(sender_number=message.text)
    await state.set_state(DepositState.waiting_for_trxid) 
    
    data = await state.get_data()
    amount = data.get("deposit_amount")
    method_name = data.get("payment_method", "Payment")
    method_key = data.get("method_key", "bkash")
    
    admin_receiving_number = LOCAL_METHODS.get(method_key, {}).get("number", "Unknown")
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
    trxid = message.text
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    method_name = user_data.get("payment_method")
    amount = user_data.get("deposit_amount", 0) 
    sender_number = user_data.get("sender_number", "Unknown")
    currency = "BDT"
    
    await state.clear()
    
    deposit_id = await create_pending_deposit(
        user_id=user_id, amount=amount, method=method_name, sender_number=sender_number, trx_id=trxid
    )

    admin_text = (
        "💰 <b>NEW DEPOSIT REQUEST!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"📱 <b>Sender:</b> <code>{sender_number}</code>\n"
        f"💵 <b>Amount:</b> {amount} {currency}\n"
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

    pending_text = (
        "⏳ <b>Deposit Request Submitted!</b>\n\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"💵 <b>Amount:</b> {amount} {currency}\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
        "👨‍💻 <i>Your transaction has been securely sent to the admin. Your account will be updated once approved.</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main", style="primary")]])
    await message.answer(pending_text, reply_markup=keyboard, parse_mode="HTML")
