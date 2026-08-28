# handlers/admin.py
import time
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from config import ADMIN_IDS
# 🚀 ফায়ারবেস ফাংশন ইমপোর্ট করা হলো
from database.crud import db, get_all_products, get_product, delete_product

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Pending Deposits", callback_data="admin_deposits")],
        [
            InlineKeyboardButton(text="📦 Manage Products", callback_data="admin_products"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users")
        ],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="close_admin")]
    ])

class AddProductState(StatesGroup):
    name = State()
    price = State()
    data = State()

class AddStockState(StatesGroup):
    product_id = State()
    data = State()

class UserManageState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    action_type = None 
    target_user = None

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_button = State()

@router.message(Command("admin"))
async def show_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id): return 
    text = "👨‍💻 <b>Admin Control Panel</b>\n\nWelcome to the secure admin dashboard. Select an action below:"
    await message.answer(text, reply_markup=get_admin_menu(), parse_mode="HTML")

@router.callback_query(F.data == "close_admin")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    await callback.message.delete()

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    text = "👨‍💻 <b>Admin Control Panel</b>\n\nWelcome to the secure admin dashboard."
    await callback.message.edit_text(text, reply_markup=get_admin_menu(), parse_mode="HTML")

# --- Pending Deposits ---
@router.callback_query(F.data == "admin_deposits")
async def show_pending_deposits(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return
    
    # 🚀 ফায়ারবেস থেকে পেন্ডিং ডিপোজিট আনা হচ্ছে
    docs = db.collection('pending_deposits').where('status', '==', 'pending').stream()
    keyboard = []
    
    for doc in docs:
        data = doc.to_dict()
        trxid = doc.id
        btn_text = f"🧾 {trxid} ({data.get('method', 'Local')})"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"viewdep_{trxid}")])
        
    if not keyboard:
        await callback.answer("✅ No pending deposits right now!", show_alert=True)
        return
        
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")])
    await callback.message.edit_text("⏳ <b>Select a pending deposit to verify:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("viewdep_"))
async def view_single_deposit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    trxid = callback.data.split("_")[1]
    
    if not db: return
    doc = db.collection('pending_deposits').document(trxid).get()
    
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        await callback.answer("❌ This request was already processed.", show_alert=True)
        return
        
    data = doc.to_dict()
    amount_bdt = data.get('amount_bdt', 0)
    # BDT থেকে USD কনভার্ট (উদাহরণস্বরূপ ১২০ টাকা = ১ ডলার ধরা হলো)
    amount_usd = round(amount_bdt / 125.0, 2) if amount_bdt else 0.0
    
    text = (
        f"🔍 <b>Deposit Verification</b>\n\n"
        f"👤 <b>User ID:</b> <code>{data.get('user_id')}</code>\n"
        f"🏦 <b>Method:</b> {data.get('method')}\n"
        f"💵 <b>Amount:</b> {amount_bdt} BDT (~${amount_usd})\n"
        f"🧾 <b>TrxID:</b> <code>{trxid}</code>\n\n"
        "<i>Do you want to approve this deposit?</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"appdep_{trxid}"), InlineKeyboardButton(text="❌ Reject", callback_data=f"rejdep_{trxid}")],
        [InlineKeyboardButton(text="◀️ Back to List", callback_data="admin_deposits")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("appdep_") | F.data.startswith("rejdep_"))
async def process_deposit(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    action, trxid = callback.data.split("_")
    
    if not db: return
    doc_ref = db.collection('pending_deposits').document(trxid)
    doc = doc_ref.get()
    
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        await callback.answer("❌ Already processed.", show_alert=True)
        return
        
    data = doc.to_dict()
    user_id = data.get('user_id')
    amount_bdt = data.get('amount_bdt', 0)
    amount_usd = round(amount_bdt / 125.0, 2)
    
    if action == "appdep":
        # ব্যালেন্স অ্যাড এবং স্ট্যাটাস আপডেট
        db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
        doc_ref.update({'status': 'approved'})
        
        try: await bot.send_message(user_id, f"🎉 <b>Deposit Approved!</b>\nTrxID: <code>{trxid}</code>\n<b>${amount_usd}</b> added to your wallet.", parse_mode="HTML")
        except: pass
        await callback.answer("✅ Approved!", show_alert=True)
    else:
        # রিজেক্ট করা হলো
        doc_ref.update({'status': 'rejected'})
        try: await bot.send_message(user_id, f"❌ <b>Deposit Rejected!</b>\nTrxID: <code>{trxid}</code>\nPlease contact support if this is a mistake.", parse_mode="HTML")
        except: pass
        await callback.answer("❌ Rejected!", show_alert=True)
        
    await show_pending_deposits(callback)

# --- MANAGE PRODUCTS ---
@router.callback_query(F.data == "admin_products")
async def manage_products_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    
    products = await get_all_products()
    keyboard = []
    if products:
        for pid, details in products.items():
            keyboard.append([InlineKeyboardButton(text=f"{details['name']} | Stock: {details['stock']}", callback_data=f"editp|{pid}")])
            
    keyboard.append([InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")])
    await callback.message.edit_text("📦 <b>Manage Products</b>\n\nClick on a product to edit, add stock, or delete it:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("editp|"))
async def edit_product_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Product not found!", show_alert=True)
    
    text = f"📦 <b>Product Details</b>\n\n🔹 <b>Name:</b> {product.get('name')}\n💲 <b>Price:</b> ${product.get('price')}\n📊 <b>Current Stock:</b> {product.get('stock')}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add New Stock", callback_data=f"addstk|{prod_id}")],
        [InlineKeyboardButton(text="🗑️ Delete Product", callback_data=f"delp|{prod_id}")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="admin_products")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("delp|"))
async def process_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    
    await delete_product(prod_id)
    await callback.answer("✅ Product deleted!", show_alert=True)
    await manage_products_menu(callback, FSMContext())

@router.callback_query(F.data.startswith("addstk|"))
async def add_stock_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    await state.set_state(AddStockState.data)
    await state.update_data(product_id=prod_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}")]])
    await callback.message.edit_text("📥 <b>Restock</b>\n\nSend the new data line by line:", reply_markup=keyboard, parse_mode="HTML")

@router.message(AddStockState.data)
async def process_add_stock(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    user_data = await state.get_data()
    prod_id = user_data['product_id']
    
    product = await get_product(prod_id)
    if not product: return
    
    clean_data = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    existing_data = product.get('data', [])
    existing_data.extend(clean_data)
    new_stock = len(existing_data)
    
    if db:
        db.collection('products').document(prod_id).update({
            'data': existing_data,
            'stock': new_stock,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data=f"editp|{prod_id}")]])
    await message.answer(f"✅ <b>Stock Added!</b>\nNew Total Stock: {new_stock}", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "add_new_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(AddProductState.name)
    await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.message(AddProductState.name)
async def add_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(prod_name=message.text)
    await state.set_state(AddProductState.price)
    await message.answer("💲 <b>Enter Product Price ($):</b>", parse_mode="HTML")

@router.message(AddProductState.price)
async def add_product_data(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: price = float(message.text)
    except ValueError: return await message.answer("❌ Invalid number.")
    
    await state.update_data(prod_price=price)
    await state.set_state(AddProductState.data)
    await message.answer("📥 <b>Send Delivery Data line by line:</b>", parse_mode="HTML")

@router.message(AddProductState.data)
async def save_new_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    clean_data = [line.strip() for line in message.text.strip().split("\n") if line.strip()]
    user_data = await state.get_data()
    
    new_prod_id = f"p{int(time.time() * 1000) % 100000}" 
    
    if db:
        db.collection('products').document(new_prod_id).set({
            'product_id': new_prod_id,
            'name': user_data['prod_name'],
            'price': float(user_data['prod_price']),
            'stock': len(clean_data),
            'data': clean_data,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="back_to_admin")]])
    await message.answer("✅ <b>Product Added!</b>", reply_markup=keyboard, parse_mode="HTML")

# --- USERS MANAGEMENT ---
@router.callback_query(F.data == "admin_users")
async def manage_users_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    
    users_count = 0
    if db:
        # ফায়ারবেস থেকে ইউজার সংখ্যা কাউন্ট করা
        users_count = len(list(db.collection('users').stream()))
        
    text = f"👥 <b>User Management</b>\n\n📊 <b>Total Registered Users:</b> {users_count}\n\nClick below to search for a user."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Search & Edit User", callback_data="search_user")],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "search_user")
async def search_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(UserManageState.waiting_for_user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users")]])
    await callback.message.edit_text("🔍 <b>Enter User ID:</b>", reply_markup=keyboard, parse_mode="HTML")

@router.message(UserManageState.waiting_for_user_id)
async def search_user_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit(): return await message.answer("❌ Invalid ID.")
    target_uid = message.text
    
    if not db: return
    doc = db.collection('users').document(target_uid).get()
    
    if not doc.exists:
        return await message.answer("❌ User not found in database.")
        
    user_info = doc.to_dict()
    await state.update_data(target_user=target_uid)
    
    text = (
        f"👤 <b>User Details</b>\n\n"
        f"🆔 <b>ID:</b> <code>{target_uid}</code>\n"
        f"📛 <b>Name:</b> {user_info.get('first_name', 'Unknown')}\n"
        f"💰 <b>Balance:</b> ${user_info.get('balance', 0.0):.2f}\n"
        f"💸 <b>Spent:</b> ${user_info.get('total_spent', 0.0):.2f}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Balance", callback_data=f"addbal_{target_uid}"), InlineKeyboardButton(text="➖ Deduct Balance", callback_data=f"dedbal_{target_uid}")],
        [InlineKeyboardButton(text="◀️ Back", callback_data="search_user")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("addbal_") | F.data.startswith("dedbal_"))
async def ask_balance_amount(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    action, target_uid = callback.data.split("_")
    await state.update_data(action_type=action, target_user=target_uid)
    await state.set_state(UserManageState.waiting_for_amount)
    
    action_text = "ADD to" if action == "addbal" else "DEDUCT from"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users")]])
    await callback.message.edit_text(f"💲 <b>Enter Amount to {action_text} User <code>{target_uid}</code>:</b>", reply_markup=keyboard, parse_mode="HTML")

@router.message(UserManageState.waiting_for_amount)
async def process_balance_change(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    try: amount = float(message.text)
    except ValueError: return await message.answer("❌ Invalid amount.")
    
    data = await state.get_data()
    target_uid = data['target_user']
    action = data['action_type']
    
    if not db: return
    user_ref = db.collection('users').document(str(target_uid))
    
    if action == "addbal":
        user_ref.update({'balance': firestore.Increment(amount)})
        try: await bot.send_message(target_uid, f"🎁 <b>Balance Added!</b>\nAdmin added <b>${amount}</b> to your wallet.", parse_mode="HTML")
        except: pass
    else:
        # মাইনাস করা
        user_ref.update({'balance': firestore.Increment(-amount)})
        try: await bot.send_message(target_uid, f"⚠️ <b>Balance Deducted</b>\nAdmin deducted <b>${amount}</b> from your wallet.", parse_mode="HTML")
        except: pass
        
    await state.clear()
    
    # নতুন ব্যালেন্স ইউজারকে দেখানোর জন্য
    updated_doc = user_ref.get()
    new_balance = updated_doc.to_dict().get('balance', 0.0) if updated_doc.exists else 0.0
    
    text = f"✅ <b>Success!</b>\n\n👤 <b>User:</b> <code>{target_uid}</code>\n💰 <b>New Balance:</b> ${new_balance:.2f}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --- 🚀 BROADCAST MESSAGE ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(BroadcastState.waiting_for_message)
    
    text = (
        "📢 <b>Broadcast Message</b>\n\n"
        "Send the message, photo, or video you want to broadcast."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(BroadcastState.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    
    products = await get_all_products()
    keyboard = []
    if products:
        for pid, details in products.items():
            keyboard.append([InlineKeyboardButton(text=f"🔗 Attach: {details['name']}", callback_data=f"bc_btn|{pid}")])
        
    keyboard.append([InlineKeyboardButton(text="⏭️ Send Without Button", callback_data="bc_btn|none")])
    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin")])
    
    await state.set_state(BroadcastState.waiting_for_button)
    await message.answer("🛒 <b>Attach a Product Button?</b>\n\nDo you want to attach a product link? (Select 'Send Without Button' for maintenance messages).", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(BroadcastState.waiting_for_button, F.data.startswith("bc_btn|"))
async def process_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id): return
    
    prod_id = callback.data.split("|")[1]
    user_data = await state.get_data()
    msg_id = user_data['msg_id']
    from_chat_id = user_data['from_chat_id']
    
    reply_markup = None
    if prod_id != "none":
        product = await get_product(prod_id)
        if product:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🛒 {product['name']} - ${product['price']}", callback_data=f"bcbuy_{prod_id}")]
            ])
            
    await state.clear()
    await callback.message.edit_text("⏳ <b>Broadcasting...</b>\nPlease wait.")
    
    users = []
    if db:
        users = [doc.id for doc in db.collection('users').stream()]
        
    if not users:
        users = [str(callback.from_user.id)]

    success_count = 0
    for uid in users:
        try:
            await bot.copy_message(
                chat_id=int(uid), 
                from_chat_id=from_chat_id, 
                message_id=msg_id,
                reply_markup=reply_markup
            )
            success_count += 1
        except Exception:
            pass 
            
    text = f"✅ <b>Broadcast Complete!</b>\n\nMessage successfully sent to <b>{success_count}</b> users."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Dashboard", callback_data="back_to_admin")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
