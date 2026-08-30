# handlers/profile.py
import html
import datetime # 🚀 সময়ের হিসাব করার জন্য
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import db, get_user
from google.cloud.firestore_v1.base_query import FieldFilter

router = Router()

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
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ==========================================
# 🛒 ডেডিকেটেড মাই অর্ডারস সেকশন (ফ্রি অটো-ডিলিট লজিক সহ)
# ==========================================
@router.callback_query(F.data == "menu_orders")
async def show_dedicated_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not db:
        await callback.answer("❌ Database error!", show_alert=True)
        return
        
    try:
        # ফায়ারবেস থেকে ইউজারের সব অর্ডার টেনে আনা
        orders_ref = db.collection('orders').where(filter=FieldFilter('user_id', '==', user_id)).stream()
        orders_list = list(orders_ref)
        
        if not orders_list:
            await callback.answer("❌ You haven't placed any orders yet.", show_alert=True)
            return
            
        text = "🛒 <b>Your Order History & Keys</b>\n\n"
        
        # 🚀 বর্তমান সময় (UTC) বের করা
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        valid_orders_count = 0
        
        # লুপ চালিয়ে প্রতিটি অর্ডারের বিস্তারিত বের করা
        for doc in orders_list:
            data = doc.to_dict()
            order_time = data.get('timestamp')
            
            # 🚀 বয়স চেক করা (৩০ দিনের বেশি হলে ডিলিট)
            if order_time:
                # Firestore থেকে আসা timestamp সাধারণত datetime অবজেক্ট হয়
                days_old = (now_utc - order_time).days
                if days_old > 30:
                    # ফায়ারবেস থেকে পার্মানেন্টলি ডিলিট করে দেওয়া
                    db.collection('orders').document(doc.id).delete()
                    continue # এই অর্ডারটা আর ইউজারকে দেখাবে না এবং স্কিপ করবে
            
            valid_orders_count += 1
            prod_name = html.escape(data.get('product_name', 'Unknown Product'))
            qty = data.get('qty', 1)
            price = data.get('total_price', 0.0)
            
            # ডাটাবেস থেকে ডেলিভারি হওয়া কি (Keys) গুলো বের করা
            items = data.get('items_delivered', [])
            
            if items:
                items_text = "\n".join([f"🔑 <code>{html.escape(item)}</code>" for item in items])
            else:
                items_text = "⚠️ No data/keys found."
            
            text += (
                f"<b>{valid_orders_count}. {prod_name}</b>\n"
                f"📦 <b>Qty:</b> {qty} | 💰 <b>Paid:</b> ${price}\n"
                f"📥 <b>Your Delivered Items:</b>\n{items_text}\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
            )
            
        # 🚀 যদি সব পুরোনো অর্ডার ডিলিট হয়ে যায় এবং নতুন কিছু না থাকে
        if valid_orders_count == 0:
            text = "⚠️ <b>Your order history is empty.</b>\n(Orders older than 30 days are automatically deleted to save space)."
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")] 
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        await callback.message.answer(f"⚠️ <b>Developer Alert - Error:</b> {e}")
        await callback.answer("❌ Failed to load orders.", show_alert=True)
