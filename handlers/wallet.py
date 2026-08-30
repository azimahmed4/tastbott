# handlers/wallet.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore
from database.crud import db, get_user, create_pending_deposit
from config import ADMIN_IDS

router = Router()

class DepositState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_sender = State() # 🚀 সেন্ডার নাম্বারের জন্য নতুন স্টেট
    waiting_for_trxid = State()
    payment_method = None 

@router.callback_query(F.data == "menu_wallet")
async def show_wallet(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    user_id = callback.from_user.id
    
    user_data = await get_user(user_id)
    if user_data:
        balance = user_data.get('balance', 0.0)
        total_spent = user_data.get('total_spent', 0.0)
    else:
        balance, total_spent = 0.0, 0.0
    
    username = callback.from_user.username
    user_display = f"@{username}" if username else callback.from_user.first_name
    
    text = (
        "💼 <b>My Wallet</b>\n\n"
        f"👤 <b>User:</b> {user_display}\n"
        f"🆔 <b>Account ID:</b> <code>{user_id}</code>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 <b>Current Balance:</b> <b>${balance:.2f}</b>\n"
        f"💸 <b>Total Spent:</b> <b>${total_spent:.2f}</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n\n"
        "Select an option below to manage your funds."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Money", callback_data="add_money")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "add_money")
async def deposit_money(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🏦 <b>Deposit Funds</b>\n\nChoose your preferred payment method:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟡 Binance Pay", callback_data="dep_binance")],
        [InlineKeyboardButton(text="📱 bKash / Nagad", callback_data="dep_local")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="menu_wallet")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.in_(["dep_binance", "dep_local"]))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    method_name = "Binance Pay" if callback.data == "dep_binance" else "bKash / Nagad"
    await state.update_data(payment_method=method_name)
    
    if callback.data == "dep_binance":
        await state.set_state(DepositState.waiting_for_trxid)
        instruction = (
            "🟡 <b>Binance Pay (Auto Deposit)</b>\n\n"
            "🔹 <b>Pay ID:</b> <code>123456789</code>\n"
            "⚠️ <i>Please send the exact amount and type your <b>Transaction ID (TrxID)</b> below:</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")
    else:
        await state.set_state(DepositState.waiting_for_amount)
        instruction = (
            "📱 <b>bKash / Nagad (Manual Verification)</b>\n\n"
            "🔹 <b>Minimum Deposit:</b> 20 BDT\n\n"
            "⚠️ <b>How much money do you want to deposit?</b>\n"
            "<i>(Type the amount in BDT below. Example: 100)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 20:
        return await message.answer("⚠️ Please enter a valid amount (Minimum 20 BDT):")
        
    await state.update_data(deposit_amount=int(message.text))
    await state.set_state(DepositState.waiting_for_sender)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]])
    await message.answer("📱 <b>Which number will you send money from?</b>\n<i>(Type your bKash/Nagad number below)</i>", reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_sender)
async def receive_sender(message: Message, state: FSMContext):
    await state.update_data(sender_number=message.text)
    await state.set_state(DepositState.waiting_for_trxid)
    
    data = await state.get_data()
    amount = data.get("deposit_amount")
    
    instruction = (
        "📱 <b>Payment Instructions</b>\n\n"
        f"🔹 <b>Amount to send:</b> {amount} BDT\n"
        "🔹 <b>Personal Number:</b> <code>01308618044</code>\n\n"
        "⚠️ <i>Please Send Money to the number above. After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]])
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
    
    if method_name == "Binance Pay":
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
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💼 Go to Wallet", callback_data="menu_wallet")]])
        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
    else:
        # 🚀 ডাটাবেসে সেভ করা হচ্ছে
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
            "👨‍💻 <i>Your transaction has been securely sent to the admin. Your wallet will be updated once approved.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Wallet", callback_data="menu_wallet")]])
        await message.answer(pending_text, reply_markup=keyboard, parse_mode="HTML")
