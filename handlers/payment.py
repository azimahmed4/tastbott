# handlers/payment.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from firebase_admin import firestore
from database.crud import db, get_user, get_product, create_pending_order
from config import ADMIN_IDS

router = Router()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:]) 
    
    if not db:
        return await callback.answer("❌ Database error!", show_alert=True)

    product = await get_product(prod_id)
    if not product:
        return await callback.answer("❌ Error: Product not found!", show_alert=True)
        
    total_price = round(product['price'] * qty, 2)
    
    user_data = await get_user(user_id)
    if not user_data:
        return await callback.answer("❌ Error: User profile not found!", show_alert=True)
        
    user_balance = user_data.get('balance', 0.0)
    
    if user_balance < total_price:
        return await callback.answer(f"❌ Insufficient balance! You need ${total_price}, but have ${user_balance:.2f}.", show_alert=True)

    # ১. ব্যালেন্স কাটা এবং total_spent বাড়ানো
    db.collection('users').document(str(user_id)).update({
        'balance': firestore.Increment(-total_price),
        'total_spent': firestore.Increment(total_price)
    })
    
    # ২. পেন্ডিং অর্ডার তৈরি করা
    order_id = await create_pending_order(
        user_id=user_id,
        product_id=prod_id,
        product_name=product['name'],
        qty=qty,
        total_price=total_price
    )
    
    new_balance = round(user_balance - total_price, 2)

    # ৩. অ্যাডমিনদের কাছে ডিরেক্ট নোটিফিকেশন পাঠানো
    admin_text = (
        "🔔 <b>NEW ORDER RECEIVED!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Paid:</b> ${total_price}\n\n"
        "<i>Check the Admin Panel to deliver the product.</i>"
    )
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Deliver Now", callback_data=f"vieword_{order_id}")]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
        except Exception:
            pass

    # ৪. ইউজারকে সাকসেস মেসেজ দেখানো
    success_text = (
        "✅ <b>Order Placed Successfully!</b>\n\n"
        f"📦 <b>Product:</b> {product['name']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Total Paid:</b> ${total_price}\n"
        f"💎 <b>Remaining Balance:</b> ${new_balance:.2f}\n\n"
        "👨‍💻 <i>Your order has been sent to the admin. You will receive your access details here very soon!</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
