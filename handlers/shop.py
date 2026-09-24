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
ORDERS_PER_PAGE = 3 

# ==========================================
# 📌 States
# ==========================================
class InvoiceSearchState(StatesGroup):
    waiting_for_invoice = State()

# 🟢 NEW: Custom Quantity State
class CustomQtyState(StatesGroup):
    waiting_for_qty = State()

# ==========================================
# 🛒 SHOP MAIN MENU (Clean & Original)
# ==========================================
@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category:"
    
    # বাটন আগে যেমন ছিল, ঠিক তেমনই রাখা হয়েছে, শুধু প্রক্সি চেকার অ্যাড করা হলো
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn", style="primary"),
            InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy", style="primary")
        ],
        [
            InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub", style="primary"),
            InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai", style="primary")
        ],
        [
            InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders|0", style="primary"),
            InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", style="primary")
        ],
        [
            InlineKeyboardButton(text="📡 All Proxy Checker", callback_data="check_proxy", style="success")
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==========================================
# 📦 MY ORDERS & INVOICE SEARCH
# ==========================================
@router.callback_query(F.data.startswith("my_orders|"))
async def view_my_orders(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    page = int(callback.data.split("|")[1])
    
    if not db: return await callback.answer("Database Error", show_alert=True)
    
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
        status = "✅ Delivered" if 'items_delivered' in o and o['items_delivered'] else "⏳ Processing"
        text += (
            f"🧾 <b>Invoice:</b> <code>{o.get('invoice_id', o.get('order_id'))}</code>\n"
            f"🛍️ <b>Item:</b> {o.get('product_name')} (x{o.get('qty')})\n"
            f"💰 <b>Total:</b> ${o.get('total_price')}\n"
            f"📊 <b>Status:</b> {status}\n"
        )
        
        if 'items_delivered' in o and o['items_delivered']:
            text += f"🎁 <b>Delivery Details:</b>\n"
            for item in o['items_delivered']:
                text += f"<code>{item}</code>\n"
                
        text += f"➖➖➖➖➖➖➖➖\n"
        
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
    
    order = None
    status = ""
    docs = db.collection('orders').where('invoice_id', '==', invoice_id).limit(1).stream()
    for d in docs: 
        order = d.to_dict()
        status = "✅ Delivered / Success"
        
    if not order:
        docs = db.collection('pending_orders').where('invoice_id', '==', invoice_id).limit(1).stream()
        for d in docs:
            order = d.to_dict()
            status = "⏳ Processing / Pending"
            
    if not order:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="search_invoice")]])
        return await message.answer(f"❌ <b>Invoice Not Found!</b>\nPlease check the ID: <code>{invoice_id}</code>", reply_markup=keyboard, parse_mode="HTML")
        
    text = (
        f"✔️ <b>ORDER STATUS</b>\n\n"
        f"🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n"
        f"📊 <b>Status:</b> {status}\n"
        f"👤 <b>User ID:</b> <code>{order.get('user_id')}</code>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🛒 <b>Item:</b> {order.get('product_name')}\n"
        f"🔢 <b>Qty:</b> {order.get('qty')}\n"
        f"💰 <b>Price:</b> ${order.get('total_price')}\n"
        f"🛡️ <b>Completed by:</b> {order.get('completed_by', 'System' if 'items_delivered' in order else 'Pending')}\n"
    )
    
    if 'items_delivered' in order and order['items_delivered']:
        text += f"\n🎁 <b>Delivery Details:</b>\n"
        for item in order['items_delivered']:
            text += f"<code>{item}</code>\n"
    
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
            row = [InlineKeyboardButton(text=f"📁 {subcats[i]['name']}", callback_data=f"shop_p|{cat}|{subcats[i]['subcat_id']}|0")]
            if i + 1 < len(subcats):
                row.append(InlineKeyboardButton(text=f"📁 {subcats[i+1]['name']}", callback_data=f"shop_p|{cat}|{subcats[i+1]['subcat_id']}|0"))
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu_buy")])
        await callback.message.edit_text(f"📁 <b>Select Validity/Type:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
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
        
        btn_style1 = "danger" if details1.get('status') == 'paused' else "primary"
        row = [InlineKeyboardButton(text=f"{details1['name']}", callback_data=f"buy_{pid1}", style=btn_style1)]
        
        if i + 1 < len(current_products):
            pid2, details2 = current_products[i+1]
            btn_style2 = "danger" if details2.get('status') == 'paused' else "primary"
            row.append(InlineKeyboardButton(text=f"{details2['name']}", callback_data=f"buy_{pid2}", style=btn_style2))
        keyboard.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"shop_p|{cat}|{subcat}|{page-1}"))
    if end_idx < total_products:
        nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"shop_p|{cat}|{subcat}|{page+1}"))
    
    if nav_row: keyboard.append(nav_row)
        
    back_target = f"showcat_{cat}" if cat in ['vpn', 'proxy'] else "menu_buy"
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data=back_target, style="danger")])
    
    text = "📦 <b>Select a Package:</b>" if current_products else "⚠️ <b>No products found here.</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# ==========================================
# 🛒 BUYING PROCESS (With Custom Bulk Qty)
# ==========================================
@router.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery):
    prod_id = callback.data.split("_", 1)[1]
    
    product = await get_product(prod_id)
    if not product:
        return await callback.answer("❌ Error: Product not found!", show_alert=True)
    if product.get('status') == 'paused':
        return await callback.answer("❌ This product is currently Out of Stock!", show_alert=True)
        
    await show_quantity_selector(callback, prod_id, 1)
    
@router.callback_query(F.data.startswith("buyprod_"))
async def buy_again_shortcut(callback: CallbackQuery):
    prod_id = callback.data.split("_")[1]
    
    product = await get_product(prod_id)
    if product and product.get('status') == 'paused':
        return await callback.answer("❌ This product is currently Out of Stock!", show_alert=True)
        
    await show_quantity_selector(callback, prod_id, 1)

@router.callback_query(F.data.startswith("setqty_"))
async def update_quantity(callback: CallbackQuery):
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:])
    if qty < 1: qty = 1
    await show_quantity_selector(callback, prod_id, qty)

# 🟢 NEW: Custom Quantity Handlers
@router.callback_query(F.data.startswith("customqty_"))
async def ask_custom_qty(callback: CallbackQuery, state: FSMContext):
    prod_id = callback.data.split("_", 1)[1]
    await state.update_data(custom_prod_id=prod_id)
    await state.set_state(CustomQtyState.waiting_for_qty)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"buy_{prod_id}")]])
    await callback.message.edit_text("🔢 <b>Enter the quantity you want to buy:</b>\n<i>(e.g., 50 or 100)</i>", reply_markup=keyboard, parse_mode="HTML")

@router.message(CustomQtyState.waiting_for_qty)
async def process_custom_qty(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Invalid number. Please enter a valid quantity.")
    qty = int(message.text)
    if qty < 1: qty = 1
    
    data = await state.get_data()
    prod_id = data.get('custom_prod_id')
    await state.clear()
    
    # 🟢 কলব্যাকের বদলে মেসেজ ইভেন্ট পাস করা হলো
    await show_quantity_selector(message, prod_id, qty)

# 🟢 MODIFIED: Supports both Message and CallbackQuery 
async def show_quantity_selector(event, prod_id: str, qty: int):
    is_callback = isinstance(event, CallbackQuery)
    
    product = await get_product(prod_id)
    if not product:
        msg = "❌ Error: Product not found!"
        return await event.answer(msg, show_alert=True) if is_callback else await event.answer(msg)
        
    if product.get('status') == 'paused':
        msg = "❌ This product is currently Out of Stock!"
        return await event.answer(msg, show_alert=True) if is_callback else await event.answer(msg)
    
    user_id = str(event.from_user.id)
    wallet_balance = 0.0
    if db:
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            wallet_balance = user_doc.to_dict().get('balance', 0.0)

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
        f"💰 <b>Total Price:</b> ${total_price}\n"
        f"💵 <b>Your Wallet:</b> ${wallet_balance:.2f}\n\n"
        "<i>Use +/- buttons or click the middle button to enter custom quantity:</i>"
    )
    
    # 🟢 NEW: Custom Quantity বাটন যুক্ত করা হলো
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"setqty_{qty-1}_{prod_id}"),
            InlineKeyboardButton(text=f" ✏️ {qty} (Custom) ", callback_data=f"customqty_{prod_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"setqty_{qty+1}_{prod_id}")
        ],
        [InlineKeyboardButton(text="✅ Confirm & Pay", callback_data=f"pay_{qty}_{prod_id}", style="success")],
        [InlineKeyboardButton(text="📝 View Note", callback_data=f"view_note_{prod_id}", style="primary")],
        [InlineKeyboardButton(text="◀️ Cancel", callback_data=back_btn, style="danger")]
    ])
    
    try: 
        if is_callback:
            await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except: pass 

@router.callback_query(F.data == "ignore_qty")
async def ignore_qty_click(callback: CallbackQuery):
    await callback.answer("Use + or - to change quantity.")

# ==========================================
# 📝 VIEW PRODUCT NOTE / RULES
# ==========================================
@router.callback_query(F.data.startswith("view_note_"))
async def show_product_note(callback: CallbackQuery):
    prod_id = callback.data.split("_", 2)[2]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Error loading product note.")
    
    custom_desc = product.get('description')
    
    if custom_desc:
        note_content = custom_desc
    else:
        note_content = (
            "<b>Description:</b>\n"
            "<blockquote>"
            "YOU WILL RECEIVE YOUR PURCHASE DETAILS SHORTLY AFTER CONFIRMATION.\n"
            "ACTIVATE IT ON YOUR OWN ACCOUNT BY YOURSELF.\n"
            "PAYMENT REQUIRED FOR ACTIVATION.\n"
            "WORKS ON NEW OR OLD ACCOUNTS.\n"
            "ALL PREMIUM FEATURES WILL BE UNLOCKED."
            "</blockquote>\n"
            "<b>Note:</b>\n"
            "<blockquote>"
            "✅ OFFICIAL ACTIVATION LINK / KEY\n"
            "✅ SELF REDEEM / SELF ACTIVATION\n"
            "✅ WORKS ON PERSONAL ACCOUNTS\n"
            "✅ SUPPORTS ALL DEVICES\n"
            "✅ NO ACCOUNT SHARING REQUIRED\n"
            "❌ NO WARRANTY IF RULES BROKEN\n"
            "❌ MUST BE CLAIMED WITHIN 24 HOURS\n"
            "❌ LOGIN MUST ON JUST 1 DEVICE TRY TO DON'T USE MULTIPLE.\n"
            "⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️\n"
            "<i>DO NOT OPEN THE LINK JUST TO CHECK. IF YOU DO, IT WILL BECOME INVALID.</i>"
            "</blockquote>"
        )

    text = f"📦 <b>{product['name']}</b>\n\n{note_content}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Purchase", callback_data=f"buy_{prod_id}", style="primary")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
