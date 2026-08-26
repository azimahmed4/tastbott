# handlers/wallet.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.dummy_db import USER_BALANCES, USER_SPENT, PENDING_DEPOSITS # PENDING_DEPOSITS ইমপোর্ট করা হলো

router = Router()

class DepositState(StatesGroup):
    waiting_for_trxid = State()
    payment_method = None 

@router.callback_query(F.data == "menu_wallet")
async def show_wallet(callback: CallbackQuery, state: FSMContext):
    await state.clear() 
    user_id = callback.from_user.id
    
    balance = USER_BALANCES.get(user_id, 0.0)
    total_spent = USER_SPENT.get(user_id, 0.0)
    
    username = callback.from_user.username
    user_display = f"@{username}" if username else callback.from_user.first_name
    
    text = (
        "💼 <b>My Wallet</b>\n\n"
        f"👤 <b>User:</b> {user_display}\n"
        f"🆔 <b>Account ID:</b> <code>{user_id}</code>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 <b>Current Balance:</b> <b>${balance}</b>\n"
        f"💸 <b>Total Spent:</b> <b>${total_spent}</b>\n"
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
    
    await state.set_state(DepositState.waiting_for_trxid)
    await state.update_data(payment_method=method_name)
    
    if callback.data == "dep_binance":
        instruction = (
            "🟡 <b>Binance Pay (Auto Deposit)</b>\n\n"
            "🔹 <b>Pay ID:</b> <code>123456789</code>\n"
            "🔹 <b>Network:</b> TRC20 / BEP20\n\n"
            "⚠️ <i>Please send the exact amount to the Pay ID above. Once sent, type your <b>Transaction ID (TrxID)</b> below for instant verification:</i>"
        )
    else:
        instruction = (
            "📱 <b>bKash / Nagad (Manual Verification)</b>\n\n"
            "🔹 <b>Personal Number:</b> <code>01700000000</code>\n"
            "🔹 <b>Minimum Deposit:</b> 100 BDT\n\n"
            "⚠️ <i>Please Send Money to the above number. After sending, type your <b>Transaction ID (TrxID)</b> below:</i>"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="add_money")]
    ])
    
    await callback.message.edit_text(instruction, reply_markup=keyboard, parse_mode="HTML")

@router.message(DepositState.waiting_for_trxid)
async def receive_trxid(message: Message, state: FSMContext):
    trxid = message.text
    user_id = message.from_user.id
    user_data = await state.get_data()
    method_name = user_data.get("payment_method")
    
    await state.clear()
    
    if method_name == "Binance Pay":
        demo_amount = 10.0 
        current_balance = USER_BALANCES.get(user_id, 0.0)
        USER_BALANCES[user_id] = round(current_balance + demo_amount, 2)
        
        success_text = (
            "✅ <b>Payment Verified Successfully!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n"
            f"💵 <b>Amount Added:</b> ${demo_amount}\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>New Wallet Balance:</b> <b>${USER_BALANCES[user_id]}</b>\n\n"
            "⚡ <i>Verified automatically via system.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 Go to Wallet", callback_data="menu_wallet")]
        ])
        await message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
    else:
        # 🚀 লজিক: TrxID ডাটাবেসে সেভ করা হলো
        PENDING_DEPOSITS[trxid] = {
            "user_id": user_id,
            "method": method_name
        }

        pending_text = (
            "⏳ <b>Deposit Request Pending!</b>\n\n"
            f"🏦 <b>Method:</b> {method_name}\n"
            f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
            "👨‍💻 <i>Your transaction has been securely sent to the admin for manual verification. Your wallet will be updated once approved.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Back to Wallet", callback_data="menu_wallet")]
        ])
        await message.answer(pending_text, reply_markup=keyboard, parse_mode="HTML")