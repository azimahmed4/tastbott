# handlers/payment.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from firebase_admin import firestore

# 🚀 ফায়ারবেস ইমপোর্ট করা হলো
from database.crud import db, get_user, get_product

router = Router()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:]) 
    
    if not db:
        await callback.answer("❌ Database error!", show_alert=True)
        return

    # 🚀 ফায়ারবেস থেকে লাইভ প্রোডাক্ট ডেটা আনা
    product = await get_product(prod_id)
    if not product:
        await callback.answer("❌ Error: Product not found!", show_alert=True)
        return
        
    current_stock = product.get('stock', 0)
    if current_stock < qty:
        await callback.answer(f"❌ Error: Not enough stock! Only {current_stock} left.", show_alert=True)
        return

    base_price = product.get('price', 0.0)
    if 1 <= qty <= 10: unit_price = base_price
    elif 11 <= qty <= 50: unit_price = round(base_price * 0.9, 2)
    else: unit_price = round(base_price * 0.8, 2)
        
    total_price = round(unit_price * qty, 2)
    
    # 🚀 ফায়ারবেস থেকে ইউজারের ব্যালেন্স চেক করা
    user_data = await get_user(user_id)
    if not user_data:
        await callback.answer("❌ Error: User profile not found!", show_alert=True)
        return
        
    user_balance = user_data.get('balance', 0.0)
    
    if user_balance < total_price:
        await callback.answer(f"❌ Insufficient balance! You need ${total_price}, but you have ${user_balance}.", show_alert=True)
        return

    # 🚀 রিয়েল ডেলিভারি লজিক (ডেটাবেস থেকে ডেটা তুলে নেওয়া)
    product_data = product.get('data', [])
    delivered_items_list = product_data[:qty]
    remaining_data = product_data[qty:]
    
    delivered_items_text = ""
    for item in delivered_items_list:
        delivered_items_text += f"🔑 <code>{item}</code>\n"

    # 🚀 ফায়ারবেসে সবকিছু একসাথে আপডেট করা (Batch Update)
    batch = db.batch()
    
    # ১. ইউজারের ব্যালেন্স কাটা এবং total_spent বাড়ানো
    user_ref = db.collection('users').document(str(user_id))
    batch.update(user_ref, {
        'balance': firestore.Increment(-total_price),
        'total_spent': firestore.Increment(total_price)
    })
    
    # ২. প্রোডাক্টের স্টক এবং ডেটা আপডেট করা
    product_ref = db.collection('products').document(prod_id)
    batch.update(product_ref, {
        'data': remaining_data,
        'stock': len(remaining_data)
    })
    
    # ৩. অর্ডার হিস্ট্রি সেভ করা (নতুন orders কালেকশনে)
    order_ref = db.collection('orders').document()
    batch.set(order_ref, {
        'user_id': user_id,
        'product_id': prod_id,
        'product_name': product.get('name'),
        'qty': qty,
        'total_price': total_price,
        'items_delivered': delivered_items_list,
        'timestamp': firestore.SERVER_TIMESTAMP
    })
    
    # সব আপডেট একসাথে কমিট করা
    batch.commit()

    new_balance = round(user_balance - total_price, 2)

    success_text = (
        "✅ <b>Payment Successful!</b>\n\n"
        f"📦 <b>Product:</b> {product.get('name')}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Total Paid:</b> ${total_price}\n"
        f"💎 <b>Remaining Balance:</b> ${new_balance}\n\n"
        "📥 <b>Your Delivered Products:</b>\n\n"
        f"{delivered_items_text}\n"
        "Thank you for your purchase! 🎉"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
