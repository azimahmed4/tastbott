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
            InlineKeyboardButton(text="🏦 Deposit", callback_data="menu_wallet")
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
        [InlineKeyboardButton(text="📢 OmniSub Updates & Offers", url="https://t.me/omni_sub")],
        [InlineKeyboardButton(text="📢 𝑪𝑹𝒀𝑷𝑻𝑶 𝑬𝑽𝑬𝑵𝑻 24", url="https://t.me/CRYPTOEVENT24")],
        [InlineKeyboardButton(text="👥 OmniSub Community & Support", url="https://t.me/OmniSubCSupport")], 
        [InlineKeyboardButton(text="✅ Verify", callback_data="check_join")]
    ])
