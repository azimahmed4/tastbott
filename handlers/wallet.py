# ==========================================
# File: handlers/wallet.py
# Purpose: ডিরেক্ট ডিপোজিট সিস্টেম (Crypto Auto Verify এবং Local Payment)
# ==========================================
import random
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from database.crud import db, get_user, create_pending_deposit
from config import ADMIN_IDS
# 🚀 নতুন ইমেইল পার্সার ইমপোর্ট করা হলো
from utils.email_parser import check_crypto_payment

router = Router()

# ==========================================
# ⚙️ PAYMENT METHODS CONFIGURATION
# ==========================================
CRYPTO_METHODS = {
    "binance": {"name": "Binance Pay", "pay_id": "1126025983"},
    "bybit": {"name": "Bybit Pay", "pay_id": "9876***54321"}
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
    waiting_for_amount = State()         # লোকাল পেমেন্টের অ্যামাউন্ট
    waiting_for_crypto_amount = State()  # 🚀 ক্রিপ্টোর অ্যামাউন্টের জন্য নতুন স্টেট
    waiting_for_sender = State()
    waiting_for_trxid = State()
    payment_method = None  
    method_key = None      
    method_type = None     
    expected_amount = None # 🚀 ইউনিক ফ্র্যাকশনাল অ্যামাউন্ট সেভ রাখার জন্য

# ==========================================
# 🏦 DIRECT DEPOSIT MENU 
# ==========================================
@router.callback_query(F.data == "menu_wallet")
async def show_deposit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    
    keyboard = [
        [
            InlineKeyboardButton(text=CRYPTO_METHODS["binance"]["name"], callback_data="dep_crypto_binance"),
            InlineKeyboardButton(text=CRYPTO_METHODS["bybit"]["name"], callback_data="dep_crypto_bybit")
        ],
        [
            InlineKeyboardButton(text=LOCAL_METHODS["bkash"]["name"], callback_data="dep_local_bkash"),
            InlineKeyboardButton(text=LOCAL_METHODS["nagad"]["name"], callback_data="dep_local_nagad")
        ],
        [
            InlineKeyboardButton(text=LOCAL_METHODS["rocket"]["name"], callback_data="dep_local_rocket")
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ]
    
    text = (
        "🏦 <b>Deposit Funds</b>\n\n"
        "Choose your preferred payment method below to add funds to your account:"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# ==========================================
# 🔄 PAYMENT METHOD SELECTION PROCESS
# ==========================================
@router.callback_query(F.data.startswith("dep_"))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    m_type = parts[1] 
    m_key = parts[2]  
    
    # 🚀 Crypto Flow (কত ডলার ডিপোজিট করবে সেটা জানতে চাইবে)
    if m_type == "crypto":
        method_info = CRYPTO_METHODS.get(m_key, {})
        method_name = method_info.get("name", "Crypto Payment")
        
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="crypto")
        await state.set_state(DepositState.waiting_for_crypto_amount)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
        await callback.message.edit_text(f"⚡ <b>{method_name}</b>\n\n<b>How much USDT do you want to deposit?</b>\n<i>(Example: 5)</i>", reply_markup=keyboard, parse_mode="HTML")
        
    # 🚀 Local Flow (আপনার আগের কোড)
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
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# ⚡ CRYPTO UNIQUE AMOUNT GENERATOR & AUTO-VERIFY
# ==========================================
@router.message(DepositState.waiting_for_crypto_amount)
async def receive_crypto_amount(message: Message, state: FSMContext):
    """ইউজার অ্যামাউন্ট দিলে র‍্যান্ডম সেন্ট যুক্ত করে পেমেন্ট করতে বলবে"""
    if not message.text.isdigit():
        return await message.answer("⚠️ Please enter a valid whole number (e.g., 5).")
        
    base_amount = int(message.text)
    
   # র‍্যান্ডম ফ্র্যাকশন (১ সেন্ট থেকে ২০ সেন্টের মধ্যে) তৈরি করা
    fraction = random.randint(1, 20) / 100.0
    expected_amount = round(base_amount + fraction, 2)
    
    await state.update_data(expected_amount=expected_amount)
    data = await state.get_data()
    
    method_name = data['payment_method']
    pay_id = CRYPTO_METHODS[data['method_key']]['pay_id']
    
    text = (
        f"⚡ <b>{method_name} (Auto Verification)</b>\n\n"
        f"🔹 <b>Pay ID / UID:</b> <code>{pay_id}</code>\n"
        f"🔹 <b>Amount to Send:</b> <code>{expected_amount}</code> USDT\n\n"
        f"⚠️ <b>CRITICAL INSTRUCTION:</b>\n"
        f"You MUST send EXACTLY <b>{expected_amount} USDT</b>. The extra cents ({fraction}) are used to auto-verify your payment.\n\n"
        f"<i>After sending the exact amount, click the verify button below.</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I have Paid (Verify)", callback_data="verify_crypto_payment")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "verify_crypto_payment")
async def verify_crypto_payment(callback: CallbackQuery, state: FSMContext):
    """ভেরিফাই বাটনে ক্লিক করলে ইমেইল পার্সার কল হবে"""
    data = await state.get_data()
    expected_amount = data.get("expected_amount")
    method_key = data.get("method_key")
    user_id = callback.from_user.id
    
    await callback.answer("⏳ Scanning inbox... Please wait.", show_alert=False)
    
    # 🚀 জিমেইল স্ক্যান করা হচ্ছে
    is_paid = check_crypto_payment(expected_amount, method_key)
    
    if is_paid:
        if db:
            db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(expected_amount)})
        
        success_text = (
            f"🎉 <b>Payment Verified!</b>\n\n"
            f"<b>${expected_amount}</b> has been automatically added to your wallet."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Go to Shop", callback_data="menu_buy")]])
        await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    else:
        await callback.answer("❌ Payment not found! Please wait 1-2 minutes for the email and click verify again.", show_alert=True)

# ==========================================
# 📱 LOCAL PAYMENT FLOW (আপনার আগের কোড)
# ==========================================
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 20:
        return await message.answer("⚠️ Please enter a valid amount (Minimum 20 BDT):")
        
    await state.update_data(deposit_amount=int(message.text))
    await state.set_state(DepositState.waiting_for_sender) 
    
    data = await state.get_data()
    method_name = data.get("payment_method", "Payment")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
    await message.answer(f"📱 <b>Which number will you Send Money from?</b>\n<i>(Type your {method_name} account number below)</i>", reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_sender)
async def receive_sender(message: Message, state: FSMContext):
    await state.update_data(sender_number=message.text)
    await state.set_state(DepositState.waiting_for_trxid) 
    
    data = await state.get_data()
    amount = data.get("deposit_amount")
    method_name = data.get("payment_method", "Payment")
    method_key = data.get("method_key", "bkash")
    
    admin_receiving_number = LOCAL_METHODS.get(method_key, {}).get("number", "Unknown")
    
    instruction = (
        "📱 <b>Payment Instructions</b>\n\n"
        f"🔹 <b>Method:</b> {method_name} (Send Money)\n"
        f"🔹 <b>Amount to send:</b> {amount} BDT\n"
        f"🔹 <b>Send Money To:</b> <code>{admin_receiving_number}</code>\n\n"
        "⚠️ <i>Please Send Money to the exact number above. After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
    await message.answer(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext, bot: Bot):
    trxid = message.text
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    method_name = user_data.get("payment_method")
    amount = user_data.get("deposit_amount", 0) 
    sender_number = user_data.get("sender_number", "Unknown")
    
    await state.clear()
    
    deposit_id = await create_pending_deposit(
        user_id=user_id, amount=amount, method=method_name, sender_number=sender_number, trx_id=trxid
    )

    admin_text = (
        "💰 <b>NEW DEPOSIT REQUEST!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"📱 <b>Sender:</b> <code>{sender_number}</code>\n"
        f"💵 <b>Amount:</b> {amount} BDT\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>"
    )
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Verify Now", callback_data=f"viewdep_{deposit_id}")]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
        except Exception:
            pass

    pending_text = (
        "⏳ <b>Deposit Request Submitted!</b>\n\n"
        f"🏦 <b>Method:</b> {method_name}\n"
        f"💵 <b>Amount:</b> {amount} BDT\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
        "👨‍💻 <i>Your transaction has been securely sent to the admin. Your account will be updated once approved.</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main")]])
    await message.answer(pending_text, reply_markup=keyboard, parse_mode="HTML")
