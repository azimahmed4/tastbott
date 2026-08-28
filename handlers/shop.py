# handlers/shop.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# 🚀 ফায়ারবেস ফাংশন ইমপোর্ট করা হলো
from database.crud import get_all_products, get_product

router = Router()

class OrderState(StatesGroup):
    waiting_for_quantity = State()
    product_id = None 

@router.callback_query(F.data == "menu_buy")
async def show_products(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    # 🚀 ফায়ারবেস থেকে লাইভ প্রোডাক্ট লিস্ট আনা হচ্ছে
    products = await get_all_products()
    
    keyboard = []
    if products:
        for prod_id, details in products.items():
            price_text = f"- ${details['price']} " if details['price'] > 0 else ""
            btn_text = f"📦 {details['name']} {price_text}| Stock: {details['stock']}"
            cb_data = f"buy_{prod_id}" if details['stock'] > 0 else "out_of_stock"
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])
        text = "<b>Available products</b>\nPlease select a product to proceed 🎉"
    else:
        text = "⚠️ <b>No products available right now.</b>\nPlease check back later!"
        
    keyboard.append([InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(F.data == "out_of_stock")
async def handle_out_of_stock(callback: CallbackQuery):
    await callback.answer("❌ This product is currently out of stock!", show_alert=True)

@router.callback_query(F.data.startswith("buy_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    prod_id = callback.data.split("_", 1)[1]
    
    # 🚀 ফায়ারবেস থেকে নির্দিষ্ট প্রোডাক্টের ডাটা আনা
    product = await get_product(prod_id)
    
    if not product:
        await callback.answer("❌ Error: Product not found!", show_alert=True)
        return
    
    text = (
        "⚠️ <b>Enter quantity</b>\n"
        f"How many <b>{product['name']}</b> would you like to buy\n\n"
        "🎉 <b>Bulk Discount Offers</b>\n"
        f"✅ Buy 1 - 10 → ${product['price']} each\n"
        f"✅ Buy 11 - 50 → ${round(product['price'] * 0.9, 2)} each\n"
        f"✅ Buy 51+ → ${round(product['price'] * 0.8, 2)} each"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data=f"qty_1_{prod_id}"),
            InlineKeyboardButton(text="5", callback_data=f"qty_5_{prod_id}"),
            InlineKeyboardButton(text="10", callback_data=f"qty_10_{prod_id}"),
            InlineKeyboardButton(text="20", callback_data=f"qty_20_{prod_id}")
        ],
        [
            InlineKeyboardButton(text="30", callback_data=f"qty_30_{prod_id}"),
            InlineKeyboardButton(text="50", callback_data=f"qty_50_{prod_id}"),
            InlineKeyboardButton(text="100", callback_data=f"qty_100_{prod_id}")
        ],
        [InlineKeyboardButton(text="🎉 Custom Quantity", callback_data=f"custom_qty_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="menu_buy")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# 🚀 ব্রডকাস্ট থেকে ক্লিক করলে এই হ্যান্ডলারটি কাজ করবে (মেসেজ এডিট না করে নতুন মেসেজ সেন্ড করবে)
@router.callback_query(F.data.startswith("bcbuy_"))
async def broadcast_buy_redirect(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    prod_id = callback.data.split("_", 1)[1]
    
    # 🚀 ফায়ারবেস থেকে নির্দিষ্ট প্রোডাক্টের ডাটা আনা
    product = await get_product(prod_id)
    
    if not product:
        await callback.answer("❌ Error: Product not found or deleted!", show_alert=True)
        return
    
    text = (
        "⚠️ <b>Enter quantity</b>\n"
        f"How many <b>{product['name']}</b> would you like to buy\n\n"
        "🎉 <b>Bulk Discount Offers</b>\n"
        f"✅ Buy 1 - 10 → ${product['price']} each\n"
        f"✅ Buy 11 - 50 → ${round(product['price'] * 0.9, 2)} each\n"
        f"✅ Buy 51+ → ${round(product['price'] * 0.8, 2)} each"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data=f"qty_1_{prod_id}"),
            InlineKeyboardButton(text="5", callback_data=f"qty_5_{prod_id}"),
            InlineKeyboardButton(text="10", callback_data=f"qty_10_{prod_id}"),
            InlineKeyboardButton(text="20", callback_data=f"qty_20_{prod_id}")
        ],
        [
            InlineKeyboardButton(text="30", callback_data=f"qty_30_{prod_id}"),
            InlineKeyboardButton(text="50", callback_data=f"qty_50_{prod_id}"),
            InlineKeyboardButton(text="100", callback_data=f"qty_100_{prod_id}")
        ],
        [InlineKeyboardButton(text="🎉 Custom Quantity", callback_data=f"custom_qty_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Go Back to Shop", callback_data="menu_buy")]
    ])
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("qty_"))
async def confirm_order(callback: CallbackQuery):
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:]) 
    
    # 🚀 ফায়ারবেস থেকে লাইভ ডাটা চেক করা
    product = await get_product(prod_id)
    if not product:
        await callback.answer("❌ Error: Product not found!", show_alert=True)
        return
    
    # স্টক চেক করা
    if qty > product['stock']:
        await callback.answer(f"⚠️ Only {product['stock']} items left in stock!", show_alert=True)
        return
    
    base_price = product['price']
    if 1 <= qty <= 10: unit_price = base_price
    elif 11 <= qty <= 50: unit_price = round(base_price * 0.9, 2)
    else: unit_price = round(base_price * 0.8, 2)
        
    total_price = round(unit_price * qty, 2)
    
    text = (
        "🛒 <b>Order Confirmation</b>\n\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💲 <b>Price per item:</b> ${unit_price}\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 <b>Total Amount:</b> ${total_price}\n\n"
        "Please confirm your purchase below."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm & Pay", callback_data=f"pay_{qty}_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data=f"buy_{prod_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("custom_qty_"))
async def custom_quantity_start(callback: CallbackQuery, state: FSMContext):
    prod_id = callback.data.split("_", 2)[2]
    await state.set_state(OrderState.waiting_for_quantity)
    await state.update_data(product_id=prod_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel Typing", callback_data=f"buy_{prod_id}")]
    ])
    await callback.message.answer("⌨️ <b>Please type the quantity you want to buy (e.g., 25):</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(OrderState.waiting_for_quantity)
async def process_custom_quantity(message: Message, state: FSMContext):
    user_data = await state.get_data()
    prod_id = user_data.get("product_id")
    
    # 🚀 ফায়ারবেস থেকে লাইভ ডাটা চেক করা
    product = await get_product(prod_id)
    
    if not message.text.isdigit():
        await message.answer("⚠️ Please enter a valid number (e.g., 25). Try again:")
        return
        
    qty = int(message.text)
    if qty <= 0:
        await message.answer("⚠️ Quantity must be greater than 0. Try again:")
        return
    if qty > product['stock']:
        await message.answer(f"⚠️ We only have {product['stock']} items in stock. Try a smaller number:")
        return

    await state.clear()
    
    base_price = product['price']
    if 1 <= qty <= 10: unit_price = base_price
    elif 11 <= qty <= 50: unit_price = round(base_price * 0.9, 2)
    else: unit_price = round(base_price * 0.8, 2)
        
    total_price = round(unit_price * qty, 2)
    
    text = (
        "🛒 <b>Order Confirmation</b>\n\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💲 <b>Price per item:</b> ${unit_price}\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 <b>Total Amount:</b> ${total_price}\n\n"
        "Please confirm your purchase below."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm & Pay", callback_data=f"pay_{qty}_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data=f"buy_{prod_id}")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
