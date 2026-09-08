# ==========================================
# File: keyboards/inline_menus.py
# Purpose: বটের মেইন মেনু এবং ফোর্স জয়েন মেনু
# ==========================================
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 🎨 PREMIUM EMOJI IDs (আপনার পছন্দমত পরিবর্তন করতে পারবেন)
EMOJI_CART = "5368324170671202286"
EMOJI_BOX = "5368324170671202287"
EMOJI_MONEY = "5368324170671202288"
EMOJI_USER = "5368324170671202289"
EMOJI_DONE = "5368324170671202290"

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📂 Buy Products", callback_data="menu_buy", style="success", icon_custom_emoji_id=EMOJI_CART),
            # 🚀 My Orders এর কলব্যাক আপডেট করা হয়েছে পেজিনেশনের সাথে মেলাতে
            InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders|0", style="primary", icon_custom_emoji_id=EMOJI_BOX)
        ],
        [
            InlineKeyboardButton(text="🔔 How to use", callback_data="menu_help", style="primary"),
            InlineKeyboardButton(text="🏦 Deposit", callback_data="menu_wallet", style="primary", icon_custom_emoji_id=EMOJI_MONEY)
        ],
        [
            InlineKeyboardButton(text="🎉 Refer & Earn", callback_data="menu_refer", style="primary"),
            InlineKeyboardButton(text="🔔 Support", callback_data="menu_support", style="primary")
        ],
        [
            InlineKeyboardButton(text="💻 Profile", callback_data="menu_profile", style="primary", icon_custom_emoji_id=EMOJI_USER),
            InlineKeyboardButton(text="🔗 API", callback_data="menu_api", style="primary")
        ]
    ])

def get_join_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        # 🔗 URL বাটনগুলোতে টেলিগ্রাম বাই-ডিফল্ট কালার সাপোর্ট দেয় না, তাই এগুলো নরমাল থাকবে
        [InlineKeyboardButton(text="📢 OmniSub Updates & Offers", url="https://t.me/omni_sub")],
        [InlineKeyboardButton(text="📢 𝑪𝑹𝒀𝑷𝑻𝑶 𝑬𝑽𝑬𝑵𝑻 24", url="https://t.me/CRYPTOEVENT24")],
        [InlineKeyboardButton(text="👥 OmniSub Community & Support", url="https://t.me/OmniSubCSupport")], 
        
        # ✅ ভেরিফাই বাটনে সাকসেস কালার এবং ইমোজি দেওয়া হলো
        [InlineKeyboardButton(text="✅ Verify", callback_data="check_join", style="success", icon_custom_emoji_id=EMOJI_DONE)]
    ])
