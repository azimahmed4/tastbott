# ==========================================
# File: handlers/shop.py
# Purpose: ইউজারের কেনাকাটা, মেনু এবং ইনভয়েস/অর্ডার হিস্ট্রি
# ==========================================
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from database.crud import (db, get_products_by_category, get_product, get_subcategories)

router = Router()

ITEMS_PER_PAGE = 10 
ORDERS_PER_PAGE = 3 # My Orders এ প্রতি পেজে কয়টি অর্ডার দেখাবে

# ==========================================
# 🎨 PREMIUM EMOJI IDs 
# ==========================================
EMOJI_CART = "5368324170671202286"
EMOJI_BOX = "5368324170671202287"
EMOJI_MONEY = "5368324170671202288"
EMOJI_SEARCH = "5368324170671202289"

class InvoiceSearchState(StatesGroup):
    waiting_for_invoice = State()

# ==========================================
# 🛒 SHOP MAIN MENU
# ==========================================
@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn", style="primary"),
            InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy", style="primary")
        ],
        [
            InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub", style="primary"),
            InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai", style="primary")
        ],
        # 🟢 NEW: My Orders and Search Button
        [
            InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders|0", style="primary", icon_custom_emoji_id=EMOJI_BOX),
            InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", style="primary", icon_custom_emoji_id=EMOJI_SEARCH)
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# 📦 MY ORDERS (Pagination) & INVOICE SEARCH
# ==========================================
@router.callback_query(F.data.startswith("my_orders|"))
async def view_my_orders(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    page = int(callback.data.split("|")[1])
    
    if not db: return await callback.answer("Database Error", show_alert=True)
    
    # ইউজার এর সব অর্ডার নিয়ে আসা
    docs = db.collection('orders').where('user_id', '==', int(user_id)).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    all_orders = [doc.to_dict() for doc in docs]
    
    if not all_orders:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Shop", callback_data="menu_buy")]])
        return await callback.message.edit_text("📦 <b>My Orders</b>\n\n⚠️ You haven't placed any orders yet.", reply_markup=keyboard, parse_mode="HTML")
        
    total_orders = len(all_orders)
    start_idx = page * ORDERS_PER_PAGE
    end_idx = start_idx + ORDERS_PER_PAGE
    current_orders = all_orders[start_idx:end_idx]
    
    text = f"📦 <b>My Orders (Page {page+1})</b>\n\n"
    for o in current_orders:
        status = "✅ Delivered" if 'items_delivered' in o else "⏳ Processing"
        text += (
            f"🧾 <b>Invoice:</b> <code>{o.get('invoice_id', o.get('order_id'))}</code>\n"
            f"🛍️ <b>Item:</b> {o.get('product_name')} (x{o.get('qty')})\n"
            f"💰 <b>Total:</b> ${o.get('total_price')}\n"
            f"📊 <b>Status:</b> {status}\n"
            "➖➖➖➖➖➖➖➖\n"
        )
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"my_orders|{page-1}"))
    if end_idx < total_orders:
        nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"my_orders|{page+1}"))
        
    keyboard = []
    if nav_row: keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Shop", callback_data="menu_buy")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data == "search_invoice")
async def start_invoice_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InvoiceSearchState.waiting_for_invoice)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_buy")]])
    await callback.message.edit_text("🔍 <b>Track Your Order</b>\n\nPlease enter your <b>Invoice ID</b> (e.g., INV123456...):", reply_markup=keyboard, parse_mode="HTML")

@router.message(InvoiceSearchState.waiting_for_invoice)
async def process_invoice_search(message: Message, state: FSMContext):
    invoice_id = message.text.strip().upper()
    await state.clear()
    
    if not db: return
    
    # প্রথমে Completed Orders এ খুঁজবে
    order = None
    status = ""
    docs = db.collection('orders').where('invoice_id', '==', invoice_id).limit(1).stream()
    for d in docs: 
        order = d.to_dict()
        status = "✅ Delivered / Success"
        
    # না পেলে Pending Orders এ খুঁজবে
    if not order:
        docs = db.collection('pending_orders').where('invoice_id', '==', invoice_id).limit(1).stream()
        for d in docs:
            order = d.to_dict()
            status = "⏳ Processing / Pending"
            
    if not order:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="search_invoice")]])
        return await message.answer(f"❌ <b>Invoice Not Found!</b>\nPlease check the ID: <code>{invoice_id}</code>", reply_markup=keyboard, parse_mode="HTML")
        
    # 🟢 Smart Invoice Output 
    text = (
        f"✔️ <b>ORDER STATUS</b>\n\n"
        f"🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n"
        f"📊 <b>Status:</b> {status}\n"
        f"👤 <b>User ID:</b> <code>{order.get('user_id')}</code>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🛒 <b>Item:</b> {order.get('product_name')}\n"
        f"🔢 <b>Qty:</b> {order.get('qty')}\n"
        f"💰 <b>Price:</b> ${order.get('total_price')}\n"
        f"🛡️ <b>Completed by:</b> {order.get('completed_by', 'System' if 'items_delivered' in order else 'Pending')}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Shop", callback_data="menu_buy")]])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# 📂 CATEGORY & PRODUCT BROWSING
# ==========================================
@router.callback_query(F.data.startswith("showcat_"))
async def show_subcategories_or_products(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        keyboard = []
        for i in range(0, len(subcats), 2):
            row = [InlineKeyboardButton(text=f"📂 {subcats[i]['name']}", callback_data=f"shop_p|{cat}|{subcats[i]['subcat_id']}|0")]
            if i + 1 < len(subcats):
                row.append(InlineKeyboardButton(text=f"📂 {subcats[i+1]['name']}", callback_data=f"shop_p|{cat}|{subcats[i+1]['subcat_id']}|0"))
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu_buy")])
        await callback.message.edit_text(f"📂 <b>Select Validity/Type:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        await display_products(callback, cat, "none", 0)

@router.callback_query(F.data.startswith("shop_p|"))
async def handle_pagination(callback: CallbackQuery):
    parts = callback.data.split("|")
    cat = parts[1]
    subcat = parts[2]
    page = int(parts[3])
    await display_products(callback, cat, subcat, page)

async def display_products(callback: CallbackQuery, cat: str, subcat: str, page: int):
    products_dict = await get_products_by_category(cat, subcat)
    products_list = list(products_dict.items())
    
    total_products = len(products_list)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_products = products_list[start_idx:end_idx]
    
    keyboard = []
    for i in range(0, len(current_products), 2):
        pid1, details1 = current_products[i]
        row = [InlineKeyboardButton(text=f"{details1['name']}", callback_data=f"buy_{pid1}", style="primary")]
        
        if i + 1 < len(current_products):
            pid2, details2 = current_products[i+1]
            row.append(InlineKeyboardButton(text=f"{details2['name']}", callback_data=f"buy_{pid2}", style="primary"))
        keyboard.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"shop_p|{cat}|{subcat}|{page-1}"))
    if end_idx < total_products:
        nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"shop_p|{cat}|{subcat}|{page+1}"))
    
    if nav_row: keyboard.append(nav_row)
        
    back_target = f"showcat_{cat}" if cat in ['vpn', 'proxy'] else "menu_buy"
    keyboard.append([InlineKeyboardButton(text="🏠 Back to Categories", callback_data=back_target, style="danger")])
    
    text = "📦 <b>Select a Package:</b>" if current_products else "⚠️ <b>No products found here.</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# ==========================================
# 🛒 BUYING PROCESS (Quantity Selection)
# ==========================================
@router.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery):
    prod_id = callback.data.split("_", 1)[1]
    await show_quantity_selector(callback, prod_id, 1)
    
@router.callback_query(F.data.startswith("buyprod_"))
async def buy_again_shortcut(callback: CallbackQuery):
    """Buy Again বাটন থেকে সরাসরি কোয়ান্টিটি সিলেক্টরে আসবে"""
    prod_id = callback.data.split("_")[1]
    await show_quantity_selector(callback, prod_id, 1)

@router.callback_query(F.data.startswith("setqty_"))
async def update_quantity(callback: CallbackQuery):
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:])
    if qty < 1: qty = 1
    await show_quantity_selector(callback, prod_id, qty)

async def show_quantity_selector(callback: CallbackQuery, prod_id: str, qty: int):
    product = await get_product(prod_id)
    if not product:
        return await callback.answer("❌ Error: Product not found!", show_alert=True)
    
    total_price = round(product['price'] * qty, 2)
    cat = product.get('category', 'vpn')
    subcat = product.get('sub_category', 'none')
    
    back_btn = f"shop_p|{cat}|{subcat}|0" if subcat and subcat != "none" else f"showcat_{cat}"
    
    text = (
        f"🛒 <b>Order Summary</b>\n\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"💲 <b>Unit Price:</b> ${product['price']}\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Total Price:</b> ${total_price}\n\n"
        "<i>Use the + and - buttons to adjust quantity:</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"setqty_{qty-1}_{prod_id}"),
            InlineKeyboardButton(text=f" {qty} ", callback_data="ignore_qty"),
            InlineKeyboardButton(text="➕", callback_data=f"setqty_{qty+1}_{prod_id}")
        ],
        # 🟢 এই বাটনটি payment.py ফাইলে process_payment কে ট্রিগার করবে
        [InlineKeyboardButton(text="✅ Confirm & Pay", callback_data=f"pay_{qty}_{prod_id}", style="success", icon_custom_emoji_id=EMOJI_CART)],
        [InlineKeyboardButton(text="◀️ Cancel", callback_data=back_btn, style="danger")]
    ])
    
    try: await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except: pass 

@router.callback_query(F.data == "ignore_qty")
async def ignore_qty_click(callback: CallbackQuery):
    await callback.answer("Use + or - to change quantity.")
