# handlers/profile.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import db, get_user

router = Router()

@router.callback_query(F.data == "my_profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # 🚀 ফায়ারবেস থেকে লাইভ ডেটা আনা
    user_data = await get_user(user_id)
    
    if user_data:
        balance = user_data.get('balance', 0.0)
        total_spent = user_data.get('total_spent', 0.0)
        total_referrals = user_data.get('total_referrals', 0)
        
        profile_text = (
            f"👤 <b>Your Profile</b>\n\n"
            f"📛 <b>Name:</b> {callback.from_user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            "➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>Balance:</b> ${balance:.2f}\n"
            f"💸 <b>Total Spent:</b> ${total_spent:.2f}\n"
            f"👥 <b>Total Referrals:</b> {total_referrals}\n"
        )
    else:
        profile_text = "⚠️ Profile not found in database! Please click /start again."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="HTML")

# 🚀 ফায়ারবেস থেকে অর্ডার হিস্ট্রি দেখানোর সিস্টেম
@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db:
        await callback.answer("❌ Database error!", show_alert=True)
        return
        
    # ফায়ারবেস থেকে ইউজারের সব অর্ডার আনা
    orders_ref = db.collection('orders').where('user_id', '==', user_id).stream()
    orders_list = list(orders_ref)
    
    if not orders_list:
        await callback.answer("❌ You haven't placed any orders yet.", show_alert=True)
        return
        
    text = "🛒 <b>Your Order History</b>\n\n"
    for doc in orders_list:
        data = doc.to_dict()
        text += f"📦 <b>{data.get('product_name')}</b> (Qty: {data.get('qty')}) - ${data.get('total_price')}\n"
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Profile", callback_data="my_profile")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
