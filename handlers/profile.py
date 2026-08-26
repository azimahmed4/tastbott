# handlers/profile.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
# আপনার আগের USER_ORDERS এর সাথে নতুনগুলো ইমপোর্ট করা হলো
from database.dummy_db import USER_ORDERS, USER_BALANCES, USER_SPENT, USER_REFERRALS

router = Router()

# --- 👤 Profile Section (নতুন যুক্ত করা হলো) ---
@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # ডাটাবেস থেকে ইউজারের তথ্য নেওয়া
    balance = USER_BALANCES.get(user_id, 0.0)
    spent = USER_SPENT.get(user_id, 0.0)
    ref_count = USER_REFERRALS.get(user_id, 0)
    orders = USER_ORDERS.get(user_id, [])
    orders_count = len(orders)
    
    # Username হ্যান্ডলিং
    first_name = callback.from_user.first_name
    username = callback.from_user.username
    user_display = f"@{username}" if username else "Not Set"
    
    text = (
        "👤 <b>User Profile</b>\n\n"
        f"📛 <b>Name:</b> {first_name}\n"
        f"💠 <b>Username:</b> {user_display}\n"
        f"🆔 <b>Account ID:</b> <code>{user_id}</code>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 <b>Current Balance:</b> ${balance}\n"
        f"💸 <b>Total Spent:</b> ${spent}\n"
        f"📦 <b>Total Orders:</b> {orders_count}\n"
        f"👥 <b>Total Referrals:</b> {ref_count}\n"
        "➖➖➖➖➖➖➖➖➖➖"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 View My Orders", callback_data="menu_orders")],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- 📦 Orders Section (আপনার দেওয়া পূর্বের কোড) ---
@router.callback_query(F.data == "menu_orders")
async def show_my_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    orders = USER_ORDERS.get(user_id, [])

    if not orders:
        text = (
            "📦 <b>My Orders</b>\n\n"
            "You haven't placed any orders yet. 🛒\n"
            "Go to 'Buy Products' to make your first purchase!"
        )
    else:
        text = "📦 <b>My Recent Orders</b>\n\n"
        # শেষের ৫টি অর্ডার দেখাবে (যাতে মেসেজ বেশি বড় না হয়ে যায়)
        for idx, order in enumerate(reversed(orders[-5:]), start=1):
            text += (
                f"🛍️ <b>Order #{idx}</b>\n"
                f"🔹 <b>Product:</b> {order['product_name']} (x{order['qty']})\n"
                f"💰 <b>Total Paid:</b> ${order['total_price']}\n"
                f"📥 <b>Keys/Data:</b>\n<code>{order['items']}</code>\n" # এখানে শুধু একটা \n দিয়েছি ডিজাইন ঠিক রাখতে
                "➖➖➖➖➖➖➖➖➖➖\n"
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Go to Profile", callback_data="menu_profile")], # প্রোফাইলে ব্যাক যাওয়ার বাটন
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_to_main")] # আপনার আগের মেইন মেনু বাটন
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")