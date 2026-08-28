# handlers/wallet.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

# 🚀 ফায়ারবেস ইমপোর্ট করা হলো
from database.crud import db, get_user

router = Router()

class DepositState(StatesGroup):
    waiting_for_amount = State() # 🚀 বিকাশের অ্যামাউন্টের জন্য নতুন স্টেট
    waiting_for_trxid = State()
    payment_method = None 

@router.callback_query(F.data == "menu_wallet")
async def show_wallet(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    user_id = callback.from_user.id
    
    # 🚀 ফায়ারবেস থেকে রিয়েল ব্যালেন্স আনা হচ্ছে
    user_data = await get_user(user_id)
    if user_data:
        balance = user_data.get('balance', 0.0)
        total_spent = user_data.get('total_spent', 0.0) # পরবর্তীতে শপ থেকে কিনলে এটা আপডেট হবে
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
    text = (
        "🏦 <b>Deposit Funds</b>\n\n"
        "Choose your preferred payment method below to add funds to your wallet:"
    )
    
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
            "🔹 <b>Network:</b> TRC20 / BEP20\n\n"
            "⚠️ <i>Please send the exact amount to the Pay ID above. Once sent, type your <b>Transaction ID (TrxID)</b> below for instant verification:</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]
        ])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")
    else:
        # 🚀 বিকাশের ক্ষেত্রে আগে অ্যামাউন্ট চাইবে
        await state.set_state(DepositState.waiting_for_amount)
        instruction = (
            "📱 <b>bKash / Nagad (Manual Verification)</b>\n\n"
            "🔹 <b>Minimum Deposit:</b> 100 BDT\n\n"
            "⚠️ <b>How much money do you want to deposit?</b>\n"
            "<i>(Please type the amount in BDT below. Example: 500)</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]
        ])
        await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

# 🚀 অ্যামাউন্ট রিসিভ করার নতুন হ্যান্ডলার
@router.message(DepositState.waiting_for_amount)
async def receive_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 100:
        await message.answer("⚠️ Please enter a valid amount (Minimum 100 BDT). Try again:")
        return
        
    amount = int(message.text)
    await state.update_data(deposit_amount=amount)
    
    # অ্যামাউন্ট সেভ করে TrxID স্টেটে পাঠিয়ে দেওয়া
    await state.set_state(DepositState.waiting_for_trxid)
    
    instruction = (
        "📱 <b>Payment Instructions</b>\n\n"
        f"🔹 <b>Amount to send:</b> {amount} BDT\n"
        "🔹 <b>Personal Number:</b> <code>01700000000</code>\n\n"
        "⚠️ <i>Please Send Money to the above number. After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]
    ])
    await message.answer(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext):
    trxid = message.text
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    method_name = user_data.get("payment_method")
    amount = user_data.get("deposit_amount", 0) # বিকাশের ক্ষেত্রে থাকবে
    
    await state.clear()
    
    if method_name == "Binance Pay":
        demo_amount = 10.0 
        
        # 🚀 ফায়ারবেসে অটোমেটিক ব্যালেন্স আপডেট
        if db:
            user_ref = db.collection('users').document(str(user_id))
            user_ref.update({'balance': firestore.Increment(demo_amount)})
            
            # নতুন ব্যালেন্স ইউজারকে দেখানোর জন্য
            updated_doc = user_ref.get()
            new_balance = updated_doc.to_dict().get('balance', 0.0) if updated_doc.exists else demo_amount
        else:
            new_balance = demo_amount
            
        success_text = (
            "✅ <b>Payment Verified Successfully!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n"
            f"💵 <b>Amount Added:</b> ${demo_amount}\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>New Wallet Balance:</b> <b>${new_balance:.2f}</b>\n\n"
            "⚡ <i>Verified automatically via system.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 Go to Wallet", callback_data="menu_wallet")]
        ])
        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
    else:
        # 🚀 ফায়ারবেসে পেন্ডিং লিস্টে TrxID এবং Amount সেভ করা হলো
        if db:
            db.collection('pending_deposits').document(trxid).set({
                'user_id': user_id,
                'method': method_name,
                'amount_bdt': amount,
                'status': 'pending',
                'timestamp': firestore.SERVER_TIMESTAMP
            })

        pending_text = (
            "⏳ <b>Deposit Request Pending!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"💵 <b>Amount:</b> {amount} BDT\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
            "👨‍💻 <i>Your transaction has been securely sent to the admin for manual verification. Your wallet will be updated once approved.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Back to Wallet", callback_data="menu_wallet")]
        ])
        await message.answer(pending_text, reply_markup=keyboard, parse_mode="HTML")
