# handlers/shop.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_products_by_category, get_product

router = Router()

@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery):
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category to view products:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn")],
        [InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy")],
        [InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub")],
        [InlineKeyboardButton(text="🤖 AI Subscription", callback_data="showcat_ai")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("showcat_"))
async def show_products(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    products = await get_products_by_category(cat)
    
    keyboard = []
    if products:
        for pid, details in products.items():
            # ফুল-উইডথ (এক লাইনে একটা) বাটন
            btn_text = f"💎 {details['name']} - ${details['price']}"
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy_{pid}")])
        text = f"📂 <b>{cat.upper()} Products</b>\n\nSelect a product to proceed:"
    else:
        text = f"⚠️ <b>No products available in {cat.upper()} right now.</b>"
        
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data="menu_buy")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# 🚀 ডাইনামিক কোয়ান্টিটি স্লাইডার সিস্টেম
@router.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery):
    prod_id = callback.data.split("_", 1)[1]
    await show_quantity_selector(callback, prod_id, 1)

@router.callback_query(F.data.startswith("setqty_"))
async def update_quantity(callback: CallbackQuery):
    _, qty_str, prod_id = callback.data.split("_")
    qty = int(qty_str)
    if qty < 1: qty = 1
    await show_quantity_selector(callback, prod_id, qty)

async def show_quantity_selector(callback: CallbackQuery, prod_id: str, qty: int):
    product = await get_product(prod_id)
    if not product:
        return await callback.answer("❌ Error: Product not found!", show_alert=True)
    
    total_price = round(product['price'] * qty, 2)
    cat = product.get('category', 'vpn')
    
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
        [InlineKeyboardButton(text="◀️ Back", callback_data=f"showcat_{cat}")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        pass # কোয়ান্টিটি সেম থাকলে টেলিগ্রাম এরর দেয়, সেটা ইগনোর করা হলো

@router.callback_query(F.data == "ignore_qty")
async def ignore_qty_click(callback: CallbackQuery):
    await callback.answer("Use + or - to change quantity.")
