# keyboards/inline_menus.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📂 Buy Products", callback_data="menu_buy"),
            InlineKeyboardButton(text="📦 My Orders", callback_data="menu_orders")
        ],
        [
            InlineKeyboardButton(text="🔔 How to use", callback_data="menu_help"),
            InlineKeyboardButton(text="💎 Wallet", callback_data="menu_wallet")
        ],
        [
            InlineKeyboardButton(text="🎉 Refer & Earn", callback_data="menu_refer"),
            InlineKeyboardButton(text="🔔 Support", callback_data="menu_support")
        ],
        [
            InlineKeyboardButton(text="💻 Profile", callback_data="menu_profile"),
            InlineKeyboardButton(text="🔗 API", callback_data="menu_api")
        ]
    ])

def get_join_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel 1", url="https://t.me/tast1g")],
        [InlineKeyboardButton(text="📢 Join Channel 2", url="https://t.me/tast2g")],
        [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/tastgu")], 
        [InlineKeyboardButton(text="✅ Verify", callback_data="check_join")]
    ])