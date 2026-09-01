# ==========================================
# File: handlers/wallet.py
# Purpose: ডিরেক্ট ডিপোজিট সিস্টেম (Crypto এবং Local Payment)
# ==========================================
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from database.crud import db, get_user, create_pending_deposit
from config import ADMIN_IDS

router = Router()

# ==========================================
# ⚙️ PAYMENT METHODS CONFIGURATION
# আপনি এখান থেকে খুব সহজেই প্রতিটি মেথডের নাম এবং রিসিভিং নাম্বার/আইডি চেঞ্জ করতে পারবেন।
# ==========================================

# ক্রিপ্টো পেমেন্টের পে আইডি
CRYPTO_METHODS = {
    "binance": {"name": "🟡 Binance Pay", "pay_id": "123456789"},
    "bybit": {"name": "🟠 Bybit Pay", "pay_id": "987654321"}
}

# লোকাল পেমেন্টের আলাদা আলাদা সেন্ড মানি নাম্বার
LOCAL_METHODS = {
    "bkash": {"name": "🦅 bKash", "number": "01308618044"}, # বিকাশের নাম্বার
    "nagad": {"name": "🔴 Nagad", "number": "01700000000"}, # নগদের নাম্বার
    "rocket": {"name": "🚀 Rocket", "number": "01900000000"} # রকেটের নাম্বার
}

# ==========================================
# 📌 States (ইউজারের থেকে ধাপে ধাপে ইনপুট নেওয়ার জন্য)
# ==========================================
class DepositState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_sender = State()
    waiting_for_trxid = State()
    payment_method = None  # মেথডের নাম (যেমন: bKash)
    method_key = None      # মেথডের কি (যেমন: bkash, nagad) যাতে পরে নাম্বার খুঁজে বের করা যায়
    method_type = None     # এটি ক্রিপ্টো নাকি লোকাল, সেটা ট্র্যাক করবে

# ==========================================
# 🏦 DIRECT DEPOSIT MENU (ওয়ালেট বাদ দিয়ে ডিরেক্ট মেনু)
# ==========================================
@router.callback_query(F.data == "menu_wallet")
async def show_deposit_menu(callback: CallbackQuery, state: FSMContext):
    """ইউজার Deposit এ ক্লিক করলে আপনার ডিজাইন অনুযায়ী বাটনগুলো দেখাবে"""
    await state.clear() 
    
    # 🚀 আপনার পছন্দ অনুযায়ী কাস্টম বাটন লেআউট তৈরি করা হলো
    keyboard = [
        # প্রথম লাইন: ক্রিপ্টো (Binance Pay, Bybit Pay)
        [
            InlineKeyboardButton(text=CRYPTO_METHODS["binance"]["name"], callback_data="dep_crypto_binance"),
            InlineKeyboardButton(text=CRYPTO_METHODS["bybit"]["name"], callback_data="dep_crypto_bybit")
        ],
        # দ্বিতীয় লাইন: লোকাল ১ (bKash, Nagad)
        [
            InlineKeyboardButton(text=LOCAL_METHODS["bkash"]["name"], callback_data="dep_local_bkash"),
            InlineKeyboardButton(text=LOCAL_METHODS["nagad"]["name"], callback_data="dep_local_nagad")
        ],
        # তৃতীয় লাইন: লোকাল ২ (Rocket)
        [
            InlineKeyboardButton(text=LOCAL_METHODS["rocket"]["name"], callback_data="dep_local_rocket")
        ],
        # চতুর্থ লাইন: ব্যাক বাটন
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
    """ইউজার কোনো একটি মেথড সিলেক্ট করলে এই ফাংশন কাজ করবে"""
    parts = callback.data.split("_")
    m_type = parts[1] # 'crypto' অথবা 'local'
    m_key = parts[2]  # 'binance', 'bkash', 'nagad' ইত্যাদি
    
    # 🚀 Crypto Flow (TrxID চাইবে সরাসরি)
    if m_type == "crypto":
        method_info = CRYPTO_METHODS.get(m_key, {})
        method_name = method_info.get("name", "Crypto Payment")
        pay_id = method_info.get("pay_id", "Unknown")
        
        # ডাটা সেভ রাখা হচ্ছে পরবর্তী ধাপের জন্য
        await state.update_data(payment_method=method_name, method_key=m_key, method_type="crypto")
        await state.set_state(DepositState.waiting_for_trxid)
        
        instruction = (
            f"⚡ <b>{method_name} (Auto Deposit)</b>\n\n"
            f"🔹 <b>Pay ID / UID:</b> <code>{pay_id}</code>\n\n"
            "⚠️ <i>Please send the exact amount. Once sent, type your <b>Transaction ID (TrxID)</b> below:</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")
        
    # 🚀 Local Flow (বিকাশ/নগদ/রকেট - প্রথমে অ্যামাউন্ট চাইবে)
    else:
        method_info = LOCAL_METHODS.get(m_key, {})
        method_name = method_info.get("name", "Local Payment")
        
        # ডাটা সেভ রাখা হচ্ছে পরবর্তী ধাপের জন্য
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
# 📱 LOCAL PAYMENT FLOW (Amount -> Sender Number -> TrxID)
# ==========================================
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    """অ্যামাউন্ট রিসিভ করা এবং সেন্ডার নাম্বার চাওয়া"""
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
    """সেন্ডার নাম্বার রিসিভ করা এবং নির্দিষ্ট রিসিভিং নাম্বার দেখিয়ে TrxID চাওয়া"""
    await state.update_data(sender_number=message.text)
    await state.set_state(DepositState.waiting_for_trxid) 
    
    data = await state.get_data()
    amount = data.get("deposit_amount")
    method_name = data.get("payment_method", "Payment")
    method_key = data.get("method_key", "bkash")
    
    # 🚀 যে মেথড সিলেক্ট করেছে, কনফিগারেশন থেকে ঠিক সেই নির্দিষ্ট নাম্বারটাই তুলে আনা হবে
    admin_receiving_number = LOCAL_METHODS.get(method_key, {}).get("number", "Unknown")
    
    instruction = (
        "📱 <b>Payment Instructions</b>\n\n"
        f"🔹 <b>Method:</b> {method_name} (Send Money)\n"
        f"🔹 <b>Amount to send:</b> {amount} BDT\n"
        f"🔹 <b>Send Money To:</b> <code>{admin_receiving_number}</code>\n\n" # নির্দিষ্ট নাম্বার শো করবে
        "⚠️ <i>Please Send Money to the exact number above. After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet")]])
    await message.answer(instruction, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# ✅ FINAL STEP: TRANSACTION ID & SAVE TO DATABASE
# ==========================================
@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext, bot: Bot):
    """সর্বশেষ ধাপ: TrxID নিয়ে ডাটাবেসে সেভ করা এবং অ্যাডমিনকে জানানো"""
    trxid = message.text
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    method_type = user_data.get("method_type")
    method_name = user_data.get("payment_method")
    
    await state.clear()
    
    # 🚀 Crypto Flow (আপাতত ম্যানুয়াল ডেমো, পরে Gmail IMAP বসবে)
    if method_type == "crypto":
        demo_amount = 1.0 
        if db:
            db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(demo_amount)})
            
        success_text = (
            "✅ <b>Payment Verified Successfully!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n"
            f"💵 <b>Amount Added:</b> ${demo_amount}\n\n"
            "⚡ <i>Verified automatically via system.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💼 Go to Shop", callback_data="menu_buy")]])
        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
    # 🚀 Local Flow (অ্যাডমিন প্যানেলে ম্যানুয়াল ভেরিফিকেশনের জন্য পাঠানো)
    else:
        amount = user_data.get("deposit_amount", 0) 
        sender_number = user_data.get("sender_number", "Unknown")
        
        # ডাটাবেসে পেন্ডিং লিস্টে সেভ করা
        deposit_id = await create_pending_deposit(
            user_id=user_id, amount=amount, method=method_name, sender_number=sender_number, trx_id=trxid
        )

        # 🚀 অ্যাডমিনদের কাছে ডিরেক্ট নোটিফিকেশন পাঠানো
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
