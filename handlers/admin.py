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

# ==========================================
# 📌 States
# ==========================================
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

# ==========================================
# 🎛️ Main Admin Dashboard & Deposits/Orders (অপরিবর্তিত)
# ==========================================
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

# (Pending Deposits ও Pending Orders এর কোডগুলো আগের মতোই থাকবে, স্পেস কমানোর জন্য এখানে স্কিপ করা হলো। আপনার অরিজিনাল কোডের Deposit ও Order সেকশন এখানে বসাবেন)

# ==========================================
# 🛒 Manage Products & Sub-Categories
# ==========================================
@router.callback_query(F.data == "admin_products")
async def manage_products_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 VPN", callback_data="admin_cat_vpn"),
            InlineKeyboardButton(text="🛡️ Proxy", callback_data="admin_cat_proxy")
        ],
        [
            InlineKeyboardButton(text="🎟️ Premium", callback_data="admin_cat_sub"),
            InlineKeyboardButton(text="🤖 AI Service", callback_data="admin_cat_ai")
        ],
        [InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product")],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text("📂 <b>Manage Products - Categories</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_cat_"))
async def show_category_options(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat = callback.data.split("_")[2] 
    
    keyboard = []
    # ভিপিএন বা প্রক্সি হলে সাব-ক্যাটাগরি দেখাবে
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        for sc in subcats:
            keyboard.append([InlineKeyboardButton(text=f"📂 {sc['name']}", callback_data=f"admin_subcat_{cat}_{sc['subcat_id']}")])
        
        keyboard.append([InlineKeyboardButton(text="➕ Add Sub-Category", callback_data=f"add_subcat_{cat}")])
    else:
        # প্রিমিয়াম/এআই এর জন্য সরাসরি প্রোডাক্ট দেখাবে
        if db:
            docs = db.collection('products').where('category', '==', cat).stream()
            for doc in docs:
                details = doc.to_dict()
                keyboard.append([InlineKeyboardButton(text=f"{details.get('name')} | ${details.get('price')}", callback_data=f"editp|{doc.id}")])
                
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data="admin_products")])
    await callback.message.edit_text(f"📦 <b>Manage: {cat.upper()}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# 🚀 Sub-Category Add Logic
@router.callback_query(F.data.startswith("add_subcat_"))
async def add_subcat_start(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split("_")[2]
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

# 🚀 New Product Add Logic (Updated)
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
        keyboard = [[InlineKeyboardButton(text=sc['name'], callback_data=f"setsubcat_{sc['subcat_id']}")] for sc in subcats]
        await callback.message.edit_text("📂 Select Sub-Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await state.update_data(prod_subcat="none")
        await state.set_state(AddProductState.name)
        await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("setsubcat_"))
async def add_product_name_sub(callback: CallbackQuery, state: FSMContext):
    subcat_id = callback.data.replace("setsubcat_", "")
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
    except ValueError: return await message.answer("❌ Invalid price format. Try again.")
    
    data = await state.get_data()
    new_prod_id = f"p{int(time.time() * 1000) % 100000}" 
    
    if db:
        db.collection('products').document(new_prod_id).set({
            'product_id': new_prod_id,
            'category': data['prod_category'],
            'sub_category': data['prod_subcat'],
            'name': data['prod_name'],
            'price': price,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
    await state.clear()
    await message.answer(f"✅ <b>Product Added!</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin")]]), parse_mode="HTML")

# (Users Management & Broadcast এর কোড আগের মতোই থাকবে)
