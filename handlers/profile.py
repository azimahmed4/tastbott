# ==========================================
# File: handlers/profile.py
# Purpose: ইউজারের প্রোফাইল দেখানো
# ==========================================
import html
import datetime # 🚀 সময়ের হিসাব করার জন্য
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import db, get_user
from google.cloud.firestore_v1.base_query import FieldFilter

router = Router()

# ==========================================
# 🎨 PREMIUM EMOJI IDs 
# ==========================================
EMOJI_USER = "5368324170671202289"

# ==========================================
# 👤 প্রোফাইল সেকশন
# ==========================================
@router.callback_query(F.data.in_(["my_profile", "menu_profile"]))
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # ফায়ারবেস থেকে লাইভ ডেটা আনা
    user_data = await get_user(user_id)
    
    if user_data:
        balance = user_data.get('balance', 0.0)
        total_spent = user_data.get('total_spent', 0.0)
        total_referrals = user_data.get('total_referrals', 0)
        
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
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
    ])
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ==========================================
# 🛒 ডেডিকেটেড মাই অর্ডারস সেকশন (Redirect)
# ==========================================
@router.callback_query(F.data == "menu_orders")
async def redirect_to_my_orders(callback: CallbackQuery):
    # যেহেতু shop.py তে My Orders এর অনেক সুন্দর পেজিনেশন এবং ইনভয়েস সিস্টেম করা হয়েছে, 
    # তাই কেউ profile থেকে orders দেখতে চাইলে তাকে ওই পেজিনেশন সিস্টেমেই পাঠিয়ে দেওয়া হচ্ছে।
    from .shop import view_my_orders
    callback.data = "my_orders|0"
    await view_my_orders(callback)
