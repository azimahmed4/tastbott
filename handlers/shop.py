from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_products_by_category, get_product, get_subcategories

router = Router()

ITEMS_PER_PAGE = 10 

@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery):
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn"),
            InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy")
        ],
        [
            InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub"),
            InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai")
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("showcat_"))
async def show_subcategories_or_products(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        keyboard = []
        for i in range(0, len(subcats), 2):
            row = [InlineKeyboardButton(text=f"📅 {subcats[i]['name']}", callback_data=f"shop_p|{cat}|{subcats[i]['subcat_id']}|0")]
            if i + 1 < len(subcats):
                row.append(InlineKeyboardButton(text=f"📅 {subcats[i+1]['name']}", callback_data=f"shop_p|{cat}|{subcats[i+1]['subcat_id']}|0"))
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
        row = [InlineKeyboardButton(text=f"{details1['name']}", callback_data=f"buy_{pid1}")]
        
        if i + 1 < len(current_products):
            pid2, details2 = current_products[i+1]
            row.append(InlineKeyboardButton(text=f"{details2['name']}", callback_data=f"buy_{pid2}"))
        keyboard.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"shop_p|{cat}|{subcat}|{page-1}"))
    if end_idx < total_products:
        nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"shop_p|{cat}|{subcat}|{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
        
    back_target = f"showcat_{cat}" if cat in ['vpn', 'proxy'] else "menu_buy"
    keyboard.append([InlineKeyboardButton(text="🏠 Back to Categories", callback_data=back_target)])
    
    text = "📦 <b>Select a Package:</b>" if current_products else "⚠️ <b>No products found here.</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery):
    prod_id = callback.data.split("_", 1)[1]
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
        [InlineKeyboardButton(text="✅ Confirm & Order", callback_data=f"pay_{qty}_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Back", callback_data=back_btn)]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        pass 

@router.callback_query(F.data == "ignore_qty")
async def ignore_qty_click(callback: CallbackQuery):
    await callback.answer("Use + or - to change quantity.")
