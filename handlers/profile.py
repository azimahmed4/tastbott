# handlers/profile.py
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import db, get_user
from google.cloud.firestore_v1.base_query import FieldFilter # 🚀 নতুন ফায়ারবেস ফিল্টার রুলস

router = Router()

@router.callback_query(F.data.in_(["my_profile", "menu_profile"]))
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # 🚀 ফায়ারবেস থেকে লাইভ ডেটা আনা
    user_data = await get_user(user_id)
    
    if user_data:
        balance = user_data.get('balance', 0.0)
        total_spent = user_data.get('total_spent', 0.0)
        total_referrals = user_data.get('total_referrals', 0)
        
        # html.escape ব্যবহার করা হলো যাতে নামের স্পেশাল ক্যারেক্টারে কোড ক্র্যাশ না করে
        safe_name = html.escape(callback.from_user.first_name)
        
        profile_text = (
            f"👤 <b>Your Profile</b>\n\n"
            f"📛 <b>Name:</b> {safe_name}\n"
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
    await callback.answer()

# 🚀 ফায়ারবেস থেকে অর্ডার হিস্ট্রি দেখানোর সিস্টেম (বুলেটপ্রুফ ভার্সন)
@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db:
        await callback.answer("❌ Database error!", show_alert=True)
        return
        
    try:
        # 🚀 ফায়ারবেসের লেটেস্ট FieldFilter ব্যবহার করে ইউজারের অর্ডার খোঁজা
        orders_ref = db.collection('orders').where(filter=FieldFilter('user_id', '==', user_id)).stream()
        orders_list = list(orders_ref)
        
        if not orders_list:
            await callback.answer("❌ You haven't placed any orders yet.", show_alert=True)
            return
            
        text = "🛒 <b>Your Order History</b>\n\n"
        
        for doc in orders_list:
            data = doc.to_dict()
            # প্রোডাক্টের নামে স্পেশাল ক্যারেক্টার থাকলে সেটা সেভ করা হলো
            prod_name = html.escape(data.get('product_name', 'Unknown Product'))
            qty = data.get('qty', 1)
            price = data.get('total_price', 0.0)
            
            text += f"📦 <b>{prod_name}</b> (Qty: {qty}) - ${price}\n"
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Back to Profile", callback_data="menu_profile")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        # 🚀 যদি কোনো কারণে এরর আসে, সেটা সাইলেন্ট না থেকে সরাসরি বটে মেসেজ দিয়ে দেবে!
        await callback.message.answer(f"⚠️ <b>Developer Alert - Error:</b> {e}")
        await callback.answer("❌ Failed to load orders.", show_alert=True)
