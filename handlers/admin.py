# handlers/admin.py
import time
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from config import ADMIN_IDS
from database.crud import db, get_product, delete_product, add_subcategory, get_subcategories, delete_subcategory

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ Pending Deposits", callback_data="admin_deposits"),
            InlineKeyboardButton(text="📦 Pending Orders", callback_data="admin_orders")
        ],
        [
            InlineKeyboardButton(text="🛒 Manage Products", callback_data="admin_products"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users")
        ],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="close_admin")]
    ])

class AddSubCatState(StatesGroup):
    category = State()
    name = State()

class AddProductState(StatesGroup):
    category = State()
    sub_category = State()
    name = State()
    price = State()

class DeliveryState(StatesGroup):
    waiting_for_key = State()
    order_id = State()
    prompt_msg_id = State()

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
    await message.answer("👨‍💻 <b>Admin Control Panel</b>\n\nSelect an action below:", reply_markup=get_admin_menu(), parse_mode="HTML")

@router.callback_query(F.data == "close_admin")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if is_admin(callback.from_user.id): await callback.message.delete()

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if is_admin(callback.from_user.id):
        await callback.message.edit_text("👨‍💻 <b>Admin Control Panel</b>", reply_markup=get_admin_menu(), parse_mode="HTML")

# ==========================================
# 💰 Deposit Approvals
# ==========================================
@router.callback_query(F.data == "admin_deposits")
async def show_pending_deposits(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return
    docs = db.collection('pending_deposits').where('status', '==', 'pending').stream()
    keyboard = []
    for doc in docs:
        data = doc.to_dict()
        keyboard.append([InlineKeyboardButton(text=f"🧾 {doc.id} | {data.get('amount')} BDT", callback_data=f"viewdep_{doc.id}")])
    if not keyboard:
        return await callback.answer("✅ No pending deposits right now!", show_alert=True)
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")])
    await callback.message.edit_text("⏳ <b>Pending Deposits:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("viewdep_"))
async def view_single_deposit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    trxid = callback.data.split("_")[1]
    if not db: return
    doc = db.collection('pending_deposits').document(trxid).get()
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        return await callback.answer("❌ This request was already processed.", show_alert=True)
        
    data = doc.to_dict()
    amount_bdt = data.get('amount', 0)
    amount_usd = round(amount_bdt / 125.0, 2) 
    
    text = (
        f"🔍 <b>Deposit Request</b>\n\n"
        f"👤 <b>User ID:</b> <code>{data.get('user_id')}</code>\n"
        f"🏦 <b>Method:</b> {data.get('method')}\n"
        f"📱 <b>Sender:</b> <code>{data.get('sender_number')}</code>\n"
        f"💵 <b>Amount:</b> {amount_bdt} BDT (~${amount_usd})\n"
        f"🧾 <b>TrxID:</b> <code>{data.get('trx_id')}</code>\n"
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
        await callback.answer("❌ Already processed or not found.", show_alert=True)
        return await callback.message.delete()
        
    data = doc.to_dict()
    user_id = data.get('user_id')
    amount_bdt = data.get('amount', 0)
    amount_usd = round(amount_bdt / 125.0, 2)
    
    if action == "appdep":
        db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
        doc_ref.update({'status': 'approved'})
        try: await bot.send_message(user_id, f"🎉 <b>Deposit Approved!</b>\n<b>${amount_usd}</b> added to your wallet.", parse_mode="HTML")
        except: pass
        await callback.answer("✅ Deposit Approved!", show_alert=True)
    else:
        doc_ref.update({'status': 'rejected'})
        try: await bot.send_message(user_id, f"❌ <b>Deposit Rejected!</b>\nYour request for {amount_bdt} BDT was rejected.", parse_mode="HTML")
        except: pass
        await callback.answer("❌ Deposit Rejected!", show_alert=True)
    await callback.message.delete()

# ==========================================
# 📦 Manual Delivery System
# ==========================================
@router.callback_query(F.data == "admin_orders")
async def show_pending_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return
    docs = db.collection('pending_orders').where('status', '==', 'pending').stream()
    keyboard = []
    for doc in docs:
        data = doc.to_dict()
        keyboard.append([InlineKeyboardButton(text=f"📦 {data.get('product_name')} (x{data.get('qty')})", callback_data=f"vieword_{doc.id}")])
    if not keyboard:
        return await callback.answer("✅ No pending orders right now!", show_alert=True)
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")])
    await callback.message.edit_text("⏳ <b>Pending Orders:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("vieword_"))
async def view_single_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    if not db: return
    doc = db.collection('pending_orders').document(order_id).get()
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        return await callback.answer("❌ This order was already fulfilled.", show_alert=True)
        
    data = doc.to_dict()
    text = (
        f"🛒 <b>Pending Order Details</b>\n\n👤 <b>User ID:</b> <code>{data.get('user_id')}</code>\n"
        f"📦 <b>Product:</b> {data.get('product_name')}\n🔢 <b>Quantity:</b> {data.get('qty')}\n💰 <b>Total Paid:</b> ${data.get('total_price')}\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Deliver Now", callback_data=f"deliver_{order_id}")],
        [InlineKeyboardButton(text="❌ Refund & Reject", callback_data=f"reford_{order_id}")],
        [InlineKeyboardButton(text="◀️ Back to List", callback_data="admin_orders")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("deliver_"))
async def start_delivery(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    prompt = await callback.message.edit_text(
        "📝 <b>Delivery Required!</b>\n\nPlease send the access key or instructions for this order below:", 
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_delivery")]])
    )
    await state.set_state(DeliveryState.waiting_for_key)
    await state.update_data(order_id=order_id, prompt_msg_id=prompt.message_id)

@router.callback_query(F.data == "cancel_delivery")
async def cancel_delivery(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.clear()
    await callback.message.delete()
    await callback.answer("Delivery Cancelled.")

@router.message(DeliveryState.waiting_for_key)
async def process_delivery_key(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    admin_key = message.text
    user_data = await state.get_data()
    order_id = user_data['order_id']
    prompt_msg_id = user_data['prompt_msg_id']
    if not db: return
    
    doc_ref = db.collection('pending_orders').document(order_id)
    doc = doc_ref.get()
    if doc.exists and doc.to_dict().get('status') == 'pending':
        data = doc.to_dict()
        user_id = data.get('user_id')
        delivery_text = (
            "🎉 <b>Order Successfully Fulfilled!</b>\n\n📦 <b>Product:</b> {data.get('product_name')}\n"
            f"🔢 <b>Quantity:</b> {data.get('qty')}\n➖➖➖➖➖➖➖➖➖➖\n"
            f"🔑 <b>Your Access Details:</b>\n<code>{admin_key}</code>\n➖➖➖➖➖➖➖➖➖➖\n"
        )
        try: await bot.send_message(user_id, delivery_text, parse_mode="HTML")
        except Exception: pass
        
        db.collection('orders').document(order_id).set({
            'user_id': user_id, 'product_id': data.get('product_id'), 'product_name': data.get('product_name'),
            'qty': data.get('qty'), 'total_price': data.get('total_price'), 'items_delivered': [admin_key], 
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        doc_ref.delete()
        
    await state.clear()
    try:
        await message.delete()
        await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
    except Exception: pass

@router.callback_query(F.data.startswith("reford_"))
async def refund_order(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    doc_ref = db.collection('pending_orders').document(order_id)
    doc = doc_ref.get()
    if doc.exists and doc.to_dict().get('status') == 'pending':
        data = doc.to_dict()
        user_id = data.get('user_id')
        total_price = data.get('total_price')
        db.collection('users').document(str(user_id)).update({
            'balance': firestore.Increment(total_price), 'total_spent': firestore.Increment(-total_price)
        })
        doc_ref.delete()
        try: await bot.send_message(user_id, f"⚠️ <b>Order Cancelled & Refunded!</b>\n<b>${total_price}</b> returned to wallet.", parse_mode="HTML")
        except: pass
    await callback.message.delete()
    await callback.answer("Order Rejected & Refunded!", show_alert=True)

# ==========================================
# 🛒 Manage Products & Sub-Categories
# ==========================================
@router.callback_query(F.data == "admin_products")
async def manage_products_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="admin_cat_vpn"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="admin_cat_proxy")],
        [InlineKeyboardButton(text="🎟️ Premium", callback_data="admin_cat_sub"), InlineKeyboardButton(text="🤖 AI Service", callback_data="admin_cat_ai")],
        [InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product")],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text("📂 <b>Manage Products - Categories</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_cat_"))
async def show_category_options(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat = callback.data.split("_")[2] 
    
    keyboard = []
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        for sc in subcats:
            keyboard.append([InlineKeyboardButton(text=f"📂 {sc['name']}", callback_data=f"admin_subcat|{cat}|{sc['subcat_id']}")])
        keyboard.append([InlineKeyboardButton(text="➕ Add Sub-Category", callback_data=f"add_subcat|{cat}")])
    else:
        if db:
            docs = db.collection('products').where('category', '==', cat).stream()
            for doc in docs:
                details = doc.to_dict()
                keyboard.append([InlineKeyboardButton(text=f"{details.get('name')} | ${details.get('price')}", callback_data=f"editp|{doc.id}")])
                
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data="admin_products")])
    await callback.message.edit_text(f"📦 <b>Manage: {cat.upper()}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_subcat|"))
async def show_category_products_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    parts = callback.data.split("|")
    cat = parts[1]
    subcat = parts[2]
    
    if not db: return
    docs = db.collection('products').where('category', '==', cat).where('sub_category', '==', subcat).stream()
    
    keyboard = []
    for doc in docs:
        details = doc.to_dict()
        keyboard.append([InlineKeyboardButton(text=f"{details.get('name', 'Unknown')} | ${details.get('price', 0.0)}", callback_data=f"editp|{doc.id}")])
        
    keyboard.append([InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product")])
    # 🚀 নতুন বাটন: অ্যাডমিন এখান থেকে সাব-ক্যাটাগরি ডিলিট করতে পারবেন
    keyboard.append([InlineKeyboardButton(text="🗑️ Delete Sub-Category", callback_data=f"delsubcat|{cat}|{subcat}")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data=f"admin_cat_{cat}")])
    
    text = f"📦 <b>Manage Products</b>\n\nSelect a product to edit or delete:"
    if len(keyboard) == 3: # শুধু Add, Delete, Back বাটন থাকলে
        text = f"⚠️ <b>No products found here.</b>"
        
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# 🚀 নতুন ফাংশন: সাব-ক্যাটাগরি ডিলিট করার লজিক
@router.callback_query(F.data.startswith("delsubcat|"))
async def process_delete_subcat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    parts = callback.data.split("|")
    cat = parts[1]
    subcat = parts[2]
    
    await delete_subcategory(subcat)
    await callback.answer("✅ Sub-Category deleted successfully!", show_alert=True)
    
    # ডিলিট করার পর মূল ক্যাটাগরিতে ফেরত পাঠানো
    callback.data = f"admin_cat_{cat}"
    await show_category_options(callback)

@router.callback_query(F.data.startswith("editp|"))
async def edit_product_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Product not found!", show_alert=True)
    
    cat = product.get('category', 'vpn')
    subcat = product.get('sub_category', 'none')
    back_btn = f"admin_subcat|{cat}|{subcat}" if subcat and subcat != "none" else f"admin_cat_{cat}"
    
    text = f"📦 <b>Product Details</b>\n\n🔹 <b>Name:</b> {product.get('name')}\n📂 <b>Category:</b> {cat.upper()}\n💲 <b>Price:</b> ${product.get('price')}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Delete Product", callback_data=f"delp|{prod_id}")],
        [InlineKeyboardButton(text="◀️ Back", callback_data=back_btn)]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("delp|"))
async def process_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    
    product = await get_product(prod_id)
    cat = product.get('category', 'vpn') if product else 'vpn'
    subcat = product.get('sub_category', 'none') if product else 'none'
    
    await delete_product(prod_id)
    await callback.answer("✅ Product deleted!", show_alert=True)
    
    if subcat and subcat != "none":
        callback.data = f"admin_subcat|{cat}|{subcat}"
        await show_category_products_sub(callback)
    else:
        callback.data = f"admin_cat_{cat}"
        await show_category_options(callback)

# --- Add Sub Category ---
@router.callback_query(F.data.startswith("add_subcat|"))
async def add_subcat_start(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split("|")[1]
    await state.update_data(category=cat)
    await state.set_state(AddSubCatState.name)
    await callback.message.edit_text(f"📝 Enter name for new <b>{cat.upper()}</b> sub-category (e.g., 7 Days Validity):", parse_mode="HTML")

@router.message(AddSubCatState.name)
async def save_subcat(message: Message, state: FSMContext):
    data = await state.get_data()
    cat = data['category']
    await add_subcategory(cat, message.text)
    await state.clear()
    await message.answer(f"✅ Sub-category added to {cat.upper()}!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data=f"admin_cat_{cat}")]]))

# --- Add Product ---
@router.callback_query(F.data == "add_new_product")
async def add_product_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="setcat_vpn"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="setcat_proxy")],
        [InlineKeyboardButton(text="🎟️ Premium", callback_data="setcat_sub"), InlineKeyboardButton(text="🤖 AI Service", callback_data="setcat_ai")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_products")]
    ])
    await callback.message.edit_text("📂 <b>Select a Category for the new product:</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("setcat_"))
async def add_product_subcat(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split("_")[1]
    await state.update_data(prod_category=cat)
    
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        if not subcats:
            return await callback.answer("⚠️ Create a sub-category first!", show_alert=True)
        keyboard = [[InlineKeyboardButton(text=sc['name'], callback_data=f"setsubcat|{sc['subcat_id']}")] for sc in subcats]
        await callback.message.edit_text("📂 Select Sub-Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await state.update_data(prod_subcat="none")
        await state.set_state(AddProductState.name)
        await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("setsubcat|"))
async def add_product_name_sub(callback: CallbackQuery, state: FSMContext):
    subcat_id = callback.data.split("|")[1]
    await state.update_data(prod_subcat=subcat_id)
    await state.set_state(AddProductState.name)
    await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.message(AddProductState.name)
async def add_product_price(message: Message, state: FSMContext):
    await state.update_data(prod_name=message.text)
    await state.set_state(AddProductState.price)
    await message.answer("💲 <b>Enter Product Price ($):</b>\n(e.g., 2.50)", parse_mode="HTML")

@router.message(AddProductState.price)
async def save_new_product(message: Message, state: FSMContext):
    try: price = float(message.text)
    except ValueError: return await message.answer("❌ Invalid price format.")
    
    data = await state.get_data()
    new_prod_id = f"p{int(time.time() * 1000) % 100000}" 
    if db:
        db.collection('products').document(new_prod_id).set({
            'product_id': new_prod_id, 'category': data['prod_category'], 'sub_category': data['prod_subcat'],
            'name': data['prod_name'], 'price': price, 'updated_at': firestore.SERVER_TIMESTAMP
        })
        
    await state.clear()
    await message.answer(f"✅ <b>Product Added!</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]]), parse_mode="HTML")

# --- Users & Broadcast ---
@router.callback_query(F.data == "admin_users")
async def manage_users_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    users_count = len(list(db.collection('users').stream())) if db else 0
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
    await callback.message.edit_text("🔍 <b>Enter User ID:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users")]]), parse_mode="HTML")

@router.message(UserManageState.waiting_for_user_id)
async def search_user_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit(): return await message.answer("❌ Invalid ID.")
    target_uid = message.text
    if not db: return
    doc = db.collection('users').document(target_uid).get()
    if not doc.exists: return await message.answer("❌ User not found.")
        
    user_info = doc.to_dict()
    await state.update_data(target_user=target_uid)
    text = (
        f"👤 <b>User Details</b>\n\n🆔 <b>ID:</b> <code>{target_uid}</code>\n📛 <b>Name:</b> {user_info.get('first_name', 'Unknown')}\n"
        f"💰 <b>Balance:</b> ${user_info.get('balance', 0.0):.2f}\n💸 <b>Spent:</b> ${user_info.get('total_spent', 0.0):.2f}"
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
    await callback.message.edit_text(f"💲 <b>Enter Amount to {action_text} User <code>{target_uid}</code>:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users")]]), parse_mode="HTML")

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
        user_ref.update({'balance': firestore.Increment(-amount)})
        try: await bot.send_message(target_uid, f"⚠️ <b>Balance Deducted</b>\nAdmin deducted <b>${amount}</b> from your wallet.", parse_mode="HTML")
        except: pass
        
    await state.clear()
    updated_doc = user_ref.get()
    new_balance = updated_doc.to_dict().get('balance', 0.0) if updated_doc.exists else 0.0
    await message.answer(f"✅ <b>Success!</b>\n\n👤 <b>User:</b> <code>{target_uid}</code>\n💰 <b>New Balance:</b> ${new_balance:.2f}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]]), parse_mode="HTML")

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.edit_text("📢 <b>Broadcast Message</b>\n\nSend the message, photo, or video you want to broadcast.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin")]]), parse_mode="HTML")

@router.message(BroadcastState.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    keyboard = []
    if db:
        for doc in db.collection('products').stream():
            details = doc.to_dict()
            keyboard.append([InlineKeyboardButton(text=f"🔗 Attach: {details['name']}", callback_data=f"bc_btn|{doc.id}")])
            
    keyboard.append([InlineKeyboardButton(text="⏭️ Send Without Button", callback_data="bc_btn|none")])
    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin")])
    await state.set_state(BroadcastState.waiting_for_button)
    await message.answer("🛒 <b>Attach a Product Button?</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(BroadcastState.waiting_for_button, F.data.startswith("bc_btn|"))
async def process_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    user_data = await state.get_data()
    msg_id = user_data['msg_id']
    from_chat_id = user_data['from_chat_id']
    
    reply_markup = None
    if prod_id != "none" and db:
        product = db.collection('products').document(prod_id).get().to_dict()
        if product:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🛒 {product['name']} - ${product['price']}", callback_data=f"bcbuy_{prod_id}")]])
            
    await state.clear()
    await callback.message.edit_text("⏳ <b>Broadcasting...</b>\nPlease wait.")
    users = [doc.id for doc in db.collection('users').stream()] if db else [str(callback.from_user.id)]
    success_count = 0
    for uid in users:
        try:
            await bot.copy_message(chat_id=int(uid), from_chat_id=from_chat_id, message_id=msg_id, reply_markup=reply_markup)
            success_count += 1
        except Exception: pass 
            
    await callback.message.edit_text(f"✅ <b>Broadcast Complete!</b>\n\nMessage sent to <b>{success_count}</b> users.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Dashboard", callback_data="back_to_admin")]]), parse_mode="HTML")
