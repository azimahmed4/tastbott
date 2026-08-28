# handlers/others.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import YOUTUBE_LINK, SUPPORT_USERNAME, BOT_USERNAME, REFERRAL_BONUS

# 🚀 ডামি ডাটাবেসের বদলে ফায়ারবেস ইমপোর্ট করা হলো
from database.crud import get_user

router = Router()

# 🔌 API Provider মেনু (এটা আপাতত কামিং সুন থাকবে)
@router.callback_query(F.data == "menu_api")
async def api_coming_soon(callback: CallbackQuery):
    await callback.answer("⏳ API provider feature is coming soon!", show_alert=True)

# 🤝 রেফার এন্ড আর্ন মেনু
@router.callback_query(F.data == "menu_refer")
async def refer_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # 🚀 ফায়ারবেস থেকে লাইভ রেফারেল ডাটা আনা হচ্ছে
    user_data = await get_user(user_id)
    ref_count = user_data.get('total_referrals', 0) if user_data else 0
    total_earned = round(ref_count * REFERRAL_BONUS, 2)
    
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    text = (
        "🤝 <b>Refer & Earn</b>\n\n"
        f"Invite your friends and earn <b>${REFERRAL_BONUS}</b> for each successful referral!\n\n"
        f"📊 <b>Your Total Referrals:</b> {ref_count}\n"
        f"💰 <b>Total Earned from Referrals:</b> ${total_earned}\n\n"
        "🔗 <b>Your Unique Referral Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "<i>(Tap the link to copy and share it with your friends)</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ❓ হাউ টু ইউজ মেনু (ফ্লেক্সিবল করা হলো)
@router.callback_query(F.data.in_(["menu_how_to_use", "menu_help"]))
async def how_to_use_menu(callback: CallbackQuery):
    text = "🎥 <b>How to Use Our Bot</b>\n\nClick the button below to watch the tutorial video on our YouTube channel."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Watch Tutorial", url=YOUTUBE_LINK)],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# 🎧 সাপোর্ট মেনু
@router.callback_query(F.data == "menu_support")
async def support_menu(callback: CallbackQuery):
    text = "🎧 <b>Customer Support</b>\n\nNeed help or facing any issues? Click the button below to message our support team."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Contact Support", url=SUPPORT_USERNAME)],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
