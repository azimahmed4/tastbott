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

class InvoiceSearchState(StatesGroup):
    waiting_for_invoice = State()

class CustomQtyState(StatesGroup):
    waiting_for_qty = State()

@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn", style="primary"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy", style="primary")],
        [InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub", style="primary"), InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai", style="primary")],
        [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders|0", style="primary"), InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", style="primary")],
        [InlineKeyboardButton(text="📡 All Proxy Checker", callback_data="check_proxy", style="success")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("my_orders|"))
async def view_my_orders(callback: CallbackQuery):
    user_id, page = str(callback.from_user.id), int(callback.data.split("|")[1])
    if not db: return await callback.answer("Database Error", show_alert=True)
    
    docs = db.collection('orders').where('user_id', '==', int(user_id)).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    all_orders = [doc.to_dict() for doc in docs]
    if not all_orders: return await callback.message.edit_text("📦 <b>My Orders</b>\n\n⚠️ You haven't placed any orders yet.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Shop", callback_data="menu_buy")]]), parse_mode="HTML")
        
    start_idx, end_idx = page * ORDERS_PER_PAGE, (page * ORDERS_PER_PAGE) + ORDERS_PER_PAGE
    current_orders = all_orders[start_idx:end_idx]
    
    text = f"📦 <b>My Orders (Page {page+1})</b>\n\n"
    for o in current_orders:
        text += f"🧾 <b>Invoice:</b> <code>{o.get('invoice_id', o.get('order_id'))}</code>\n🛍️ <b>Item:</b> {o.get('product_name')} (x{o.get('qty')})\n💰 <b>Total:</b> ${o.get('total_price')}\n📊 <b>Status:</b> {'✅ Delivered' if o.get('items_delivered') else '⏳ Processing'}\n"
        if o.get('items_delivered'):
            text += f"🎁 <b>Delivery Details:</b>\n" + "".join([f"<code>{i}</code>\n" for i in o['items_delivered']])
        text += f"➖➖➖➖➖➖➖➖\n"
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"my_orders|{page-1}"))
    if end_idx < len(all_orders): nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"my_orders|{page+1}"))
        
    keyboard = [nav_row] if nav_row else []
    keyboard.extend([[InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice")], [InlineKeyboardButton(text="◀️ Back to Shop", callback_data="menu_buy")]])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data == "search_invoice")
async def start_invoice_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InvoiceSearchState.waiting_for_invoice)
    await callback.message.edit_text("🔍 <b>Track Your Order</b>\n\nPlease enter your <b>Invoice ID</b> (e.g., INV123456...):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="menu_buy")]]), parse_mode="HTML")

@router.message(InvoiceSearchState.waiting_for_invoice)
async def process_invoice_search(message: Message, state: FSMContext):
    invoice_id = message.text.strip().upper()
    await state.clear()
    if not db: return
    
    order, status = None, ""
    for d in db.collection('orders').where('invoice_id', '==', invoice_id).limit(1).stream(): order, status = d.to_dict(), "✅ Delivered / Success"
    if not order:
        for d in db.collection('pending_orders').where('invoice_id', '==', invoice_id).limit(1).stream(): order, status = d.to_dict(), "⏳ Processing / Pending"
    if not order: return await message.answer(f"❌ <b>Invoice Not Found!</b>\nPlease check the ID: <code>{invoice_id}</code>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="search_invoice")]]), parse_mode="HTML")
        
    text = (f"✔️ <b>ORDER STATUS</b>\n\n🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n📊 <b>Status:</b> {status}\n👤 <b>User ID:</b> <code>{order.get('user_id')}</code>\n➖➖➖➖➖➖➖➖➖➖\n"
            f"🛒 <b>Item:</b> {order.get('product_name')}\n🔢 <b>Qty:</b> {order.get('qty')}\n💰 <b>Price:</b> ${order.get('total_price')}\n🛡️ <b>Completed by:</b> {order.get('completed_by', 'System' if order.get('items_delivered') else 'Pending')}\n")
    if order.get('items_delivered'): text += f"\n🎁 <b>Delivery Details:</b>\n" + "".join([f"<code>{i}</code>\n" for i in order['items_delivered']])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Shop", callback_data="menu_buy")]]), parse_mode="HTML")

@router.callback_query(F.data.startswith("showcat_"))
async def show_subcategories_or_products(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        keyboard = []
        for i in range(0, len(subcats), 2):
            row = [InlineKeyboardButton(text=f"{subcats[i]['name']}", callback_data=f"shop_p|{cat}|{subcats[i]['subcat_id']}|0", style="primary")]
            if i + 1 < len(subcats): row.append(InlineKeyboardButton(text=f"{subcats[i+1]['name']}", callback_data=f"shop_p|{cat}|{subcats[i+1]['subcat_id']}|0", style="primary"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu_buy", style="danger")])
        await callback.message.edit_text(f"📁 <b>Select Validity/Type:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        await display_products(callback, cat, "none", 0)

@router.callback_query(F.data.startswith("shop_p|"))
async def handle_pagination(callback: CallbackQuery):
    await display_products(callback, callback.data.split("|")[1], callback.data.split("|")[2], int(callback.data.split("|")[3]))

async def display_products(callback: CallbackQuery, cat: str, subcat: str, page: int):
    products_list = list((await get_products_by_category(cat, subcat)).items())
    start_idx, end_idx = page * ITEMS_PER_PAGE, (page * ITEMS_PER_PAGE) + ITEMS_PER_PAGE
    current_products = products_list[start_idx:end_idx]
    
    keyboard = []
    for i in range(0, len(current_products), 2):
        row = [InlineKeyboardButton(text=f"{current_products[i][1]['name']}", callback_data=f"buy_{current_products[i][0]}", style="danger" if current_products[i][1].get('status') == 'paused' else "primary")]
        if i + 1 < len(current_products): row.append(InlineKeyboardButton(text=f"{current_products[i+1][1]['name']}", callback_data=f"buy_{current_products[i+1][0]}", style="danger" if current_products[i+1][1].get('status') == 'paused' else "primary"))
        keyboard.append(row)
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"shop_p|{cat}|{subcat}|{page-1}"))
    if end_idx < len(products_list): nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"shop_p|{cat}|{subcat}|{page+1}"))
    if nav_row: keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data=f"showcat_{cat}" if cat in ['vpn', 'proxy'] else "menu_buy", style="danger")])
    await callback.message.edit_text("📦 <b>Select a Package:</b>" if current_products else "⚠️ <b>No products found here.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery):
    prod_id = callback.data.split("_", 1)[1]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Error: Product not found!", show_alert=True)
    if product.get('status') == 'paused': return await callback.answer("❌ This product is currently Out of Stock!", show_alert=True)
    
    # 🟢 NEW: Start with min_qty instead of 1
    min_qty = product.get('min_qty', 1)
    await show_quantity_selector(callback, prod_id, min_qty)
    
@router.callback_query(F.data.startswith("buyprod_"))
async def buy_again_shortcut(callback: CallbackQuery):
    prod_id = callback.data.split("_")[1]
    product = await get_product(prod_id)
    if product and product.get('status') == 'paused': return await callback.answer("❌ This product is currently Out of Stock!", show_alert=True)
    
    # 🟢 FIXED: Buy Again will send a NEW message instead of editing the delivery text
    min_qty = product.get('min_qty', 1)
    await show_quantity_selector(callback, prod_id, min_qty, edit_msg=False)

@router.callback_query(F.data.startswith("setqty_"))
async def update_quantity(callback: CallbackQuery):
    parts = callback.data.split("_")
    qty, prod_id = int(parts[1]), "_".join(parts[2:])
    
    # 🟢 ENFORCE MOQ ON +/- BUTTONS
    product = await get_product(prod_id)
    min_qty = product.get('min_qty', 1) if product else 1
    if qty < min_qty: qty = min_qty
    
    await show_quantity_selector(callback, prod_id, qty)

@router.callback_query(F.data.startswith("customqty_"))
async def ask_custom_qty(callback: CallbackQuery, state: FSMContext):
    prod_id = callback.data.split("_", 1)[1]
    await state.update_data(custom_prod_id=prod_id)
    await state.set_state(CustomQtyState.waiting_for_qty)
    await callback.message.edit_text("🔢 <b>Enter the quantity you want to buy:</b>\n<i>(e.g., 50 or 100)</i>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"buy_{prod_id}")]]), parse_mode="HTML")

@router.message(CustomQtyState.waiting_for_qty)
async def process_custom_qty(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("❌ Invalid number. Please enter a valid quantity.")
    qty = int(message.text)
    
    data = await state.get_data()
    prod_id = data.get('custom_prod_id')
    
    # 🟢 ENFORCE MOQ ON CUSTOM INPUT
    product = await get_product(prod_id)
    min_qty = product.get('min_qty', 1) if product else 1
    if qty < min_qty:
        return await message.answer(f"❌ <b>Error:</b> You must order at least <b>{min_qty}</b> pieces for this product!\nPlease enter a number {min_qty} or higher:", parse_mode="HTML")
        
    await state.clear()
    await show_quantity_selector(message, prod_id, qty)

# 🟢 MODIFIED: edit_msg parameter added to handle "Buy Again" perfectly
async def show_quantity_selector(event, prod_id: str, qty: int, edit_msg: bool = True):
    is_callback = isinstance(event, CallbackQuery)
    product = await get_product(prod_id)
    if not product: return await event.answer("❌ Error: Product not found!", show_alert=True) if is_callback else await event.answer("❌ Error: Product not found!")
    if product.get('status') == 'paused': return await event.answer("❌ This product is currently Out of Stock!", show_alert=True) if is_callback else await event.answer("❌ This product is currently Out of Stock!")
    
    user_doc = db.collection('users').document(str(event.from_user.id)).get() if db else None
    wallet_balance = user_doc.to_dict().get('balance', 0.0) if user_doc and user_doc.exists else 0.0

    total_price = round(product['price'] * qty, 2)
    cat, subcat = product.get('category', 'vpn'), product.get('sub_category', 'none')
    back_btn = f"shop_p|{cat}|{subcat}|0" if subcat and subcat != "none" else f"showcat_{cat}"
    
    min_qty_text = f"\n📉 <i>Min. Order Quantity: {product.get('min_qty', 1)}</i>" if product.get('min_qty', 1) > 1 else ""
    
    text = (f"🛒 <b>Order Summary</b>\n\n📦 <b>Product:</b> {product['name']}\n💲 <b>Unit Price:</b> ${product['price']}\n➖➖➖➖➖➖➖➖➖➖\n"
            f"🔢 <b>Quantity:</b> {qty}\n💰 <b>Total Price:</b> ${total_price}\n💵 <b>Your Wallet:</b> ${wallet_balance:.2f}\n{min_qty_text}\n\n<i>Use +/- buttons or click 'Enter quantity' for custom order:</i>")
            
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➖", callback_data=f"setqty_{qty-1}_{prod_id}", style="danger"), InlineKeyboardButton(text=f" {qty} ", callback_data="ignore_qty", style="primary"), InlineKeyboardButton(text="➕", callback_data=f"setqty_{qty+1}_{prod_id}", style="success")],
        [InlineKeyboardButton(text="Enter quantity", callback_data=f"customqty_{prod_id}", style="primary")],
        [InlineKeyboardButton(text="✅ Confirm & Pay", callback_data=f"pay_{qty}_{prod_id}", style="success")],
        [InlineKeyboardButton(text="📝 View Note", callback_data=f"view_note_{prod_id}", style="primary")],
        [InlineKeyboardButton(text="◀️ Cancel", callback_data=back_btn, style="danger")]
    ])
    
    try: 
        if is_callback:
            if edit_msg: await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            else: await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML") # For Buy Again
        else: await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except: pass 

@router.callback_query(F.data == "ignore_qty")
async def ignore_qty_click(callback: CallbackQuery): await callback.answer("Use + or - to change quantity.")

@router.callback_query(F.data.startswith("view_note_"))
async def show_product_note(callback: CallbackQuery):
    prod_id = callback.data.split("_", 2)[2]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Error loading product note.")
    
    note_content = product.get('description') or ("<b>Description:</b>\n<blockquote>YOU WILL RECEIVE YOUR PURCHASE DETAILS SHORTLY AFTER CONFIRMATION.\nACTIVATE IT ON YOUR OWN ACCOUNT BY YOURSELF.\nPAYMENT REQUIRED FOR ACTIVATION.\nWORKS ON NEW OR OLD ACCOUNTS.\nALL PREMIUM FEATURES WILL BE UNLOCKED.</blockquote>\n"
        "<b>Note:</b>\n<blockquote>✅ OFFICIAL ACTIVATION LINK / KEY\n✅ SELF REDEEM / SELF ACTIVATION\n✅ WORKS ON PERSONAL ACCOUNTS\n✅ SUPPORTS ALL DEVICES\n✅ NO ACCOUNT SHARING REQUIRED\n❌ NO WARRANTY IF RULES BROKEN\n❌ MUST BE CLAIMED WITHIN 24 HOURS\n❌ LOGIN MUST ON JUST 1 DEVICE TRY TO DON'T USE MULTIPLE.\n⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️\n<i>DO NOT OPEN THE LINK JUST TO CHECK. IF YOU DO, IT WILL BECOME INVALID.</i></blockquote>")

    await callback.message.edit_text(f"📦 <b>{product['name']}</b>\n\n{note_content}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Purchase", callback_data=f"buy_{prod_id}", style="primary")]]), parse_mode="HTML")
