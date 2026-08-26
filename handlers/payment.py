# handlers/payment.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.dummy_db import PRODUCTS, USER_BALANCES, USER_SPENT, USER_ORDERS

router = Router()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:]) 
    
    product = PRODUCTS.get(prod_id)
    if product['stock'] < qty:
        await callback.answer(f"❌ Error: Not enough stock! Only {product['stock']} left.", show_alert=True)
        return

    base_price = product['price']
    if 1 <= qty <= 10: unit_price = base_price
    elif 11 <= qty <= 50: unit_price = round(base_price * 0.9, 2)
    else: unit_price = round(base_price * 0.8, 2)
        
    total_price = round(unit_price * qty, 2)
    user_balance = USER_BALANCES.get(user_id, 0.0)
    
    if user_balance < total_price:
        await callback.answer(f"❌ Insufficient balance! You need ${total_price}, but you have ${user_balance}.", show_alert=True)
        return

    # টাকা কাটা
    USER_BALANCES[user_id] = round(user_balance - total_price, 2)
    
    current_spent = USER_SPENT.get(user_id, 0.0)
    USER_SPENT[user_id] = round(current_spent + total_price, 2)

    # 🚀 রিয়েল ডেলিভারি লজিক (ডাটাবেস থেকে একটা একটা করে ডেটা তুলে নেওয়া)
    delivered_items = ""
    for _ in range(qty):
        if product['data']:
            item = product['data'].pop(0) # লিস্টের প্রথম আইটেমটা নিয়ে নিবে এবং মুছে ফেলবে
            delivered_items += f"🔑 <code>{item}</code>\n"
        else:
            break
            
    # স্টক আপডেট করা (লিস্টে আর কয়টা ডেটা অবশিষ্ট আছে)
    product['stock'] = len(product['data'])

    # অর্ডার হিস্টোরি সেভ করা
    if user_id not in USER_ORDERS:
        USER_ORDERS[user_id] = []
        
    USER_ORDERS[user_id].append({
        "product_name": product['name'],
        "qty": qty,
        "total_price": total_price,
        "items": delivered_items
    })

    success_text = (
        "✅ <b>Payment Successful!</b>\n\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Total Paid:</b> ${total_price}\n"
        f"💎 <b>Remaining Balance:</b> ${USER_BALANCES[user_id]}\n\n"
        "📥 <b>Your Delivered Products:</b>\n\n"
        f"{delivered_items}\n"
        "Thank you for your purchase! 🎉"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")