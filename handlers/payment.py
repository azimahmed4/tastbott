# ==========================================
# File: handlers/payment.py
# Purpose: ইউজারের পেমেন্ট কনফার্মেশন, ব্যালেন্স কাটা, অটো/ম্যানুয়াল ডেলিভারি এবং ইনভয়েস তৈরি
# ==========================================
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from firebase_admin import firestore
from database.crud import db, get_user, get_product, create_pending_order, generate_invoice_id

# 🟢 NEW: MAIN_GROUPS_ID ইমপোর্ট করা হলো রিয়েল সেলস অ্যালার্ট পাঠানোর জন্য
from config import ADMIN_IDS, BOT_USERNAME, MAIN_GROUPS_ID 

router = Router()

# ==========================================
# 🎨 PREMIUM EMOJI IDs 
# ==========================================
EMOJI_CART = "5368324170671202286"
EMOJI_DONE = "5368324170671202287"
EMOJI_SEARCH = "5368324170671202289"

# ==========================================
# 🟢 SMART DELIVERY FORMATTER
# ==========================================
def format_delivery_text(category: str, raw_data: str) -> str:
    """ক্যাটাগরি অনুযায়ী ডেলিভারি মেসেজ সুন্দর করে সাজানোর ফাংশন"""
    cat = category.lower()
    parts = raw_data.split(":")
    
    if cat == "proxy" and len(parts) >= 4:
        return (
            f"🌐 <b>IP:</b> <code>{parts[0].strip()}</code>\n"
            f"🔌 <b>Port:</b> <code>{parts[1].strip()}</code>\n"
            f"👤 <b>User:</b> <code>{parts[2].strip()}</code>\n"
            f"🔑 <b>Pass:</b> <code>{':'.join(parts[3:]).strip()}</code>"
        )
    elif cat == "vpn" and len(parts) >= 2:
        return (
            f"📧 <b>Mail:</b> <code>{parts[0].strip()}</code>\n"
            f"🔐 <b>Pass:</b> <code>{':'.join(parts[1:]).strip()}</code>"
        )
    else:
        # Subscription বা অন্য যেকোনো ফরম্যাটের জন্য ডিফল্ট
        return f"🔗 <b>Link/Key:</b> <code>{raw_data}</code>"

# 🟢 NEW: রিয়েল সেলস অ্যালার্ট পাঠানোর ফাংশন
async def send_real_sales_alert(bot: Bot, product_id: str, product_name: str, user_id: int):
    """রিয়েল টাইম সেলস অ্যালার্ট গ্রুপে পাঠানোর ফাংশন"""
    if not MAIN_GROUPS_ID:
        return
        
    try:
        # ইউজারের আইডি মাস্ক করা (e.g., 105***78)
        str_uid = str(user_id)
        if len(str_uid) > 4:
            masked_uid = f"{str_uid[:3]}***{str_uid[-2:]}"
        else:
            masked_uid = f"{str_uid[:1]}***{str_uid[-1:]}"
            
        promo_text = (
            f"🎉 <b>New Order Placed!</b>\n\n"
            f"👤 User <code>{masked_uid}</code> just purchased:\n"
            f"🛍️ <b>{product_name}</b>\n\n"
            f"⚡️ <i>Delivered automatically in seconds.</i>"
        )
        
        buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
        buy_btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]
        ])
        
        await bot.send_message(
            chat_id=MAIN_GROUPS_ID,
            text=promo_text,
            parse_mode="HTML",
            reply_markup=buy_btn
        )
    except Exception as e:
        pass # গ্রুপে অ্যালার্ট পাঠাতে ফেইল করলে মেইন প্রসেস যেন ক্র্যাশ না করে

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
    cat_name = product.get('category', 'unknown') 
    
    user_data = await get_user(user_id)
    if not user_data:
        return await callback.answer("❌ Error: User profile not found!", show_alert=True)
        
    user_balance = float(user_data.get('balance', 0.0))
    
    if user_balance < total_price:
        return await callback.answer(f"❌ Insufficient balance! You need ${total_price}, but have ${user_balance:.2f}.", show_alert=True)

    # ১. ব্যালেন্স কাটা এবং total_spent বাড়ানো
    db.collection('users').document(str(user_id)).update({
        'balance': firestore.Increment(-total_price),
        'total_spent': firestore.Increment(total_price)
    })
    
    delivery_type = product.get('delivery_type', 'manual')
    stock_list = product.get('stock', [])
    
    # 🟢 AUTO DELIVERY LOGIC (স্টক থাকলে সাথে সাথে ডেলিভারি)
    if delivery_type == "auto" and len(stock_list) >= qty:
        delivered_items = stock_list[:qty]
        remaining_stock = stock_list[qty:]
        
        # ডাটাবেসে স্টক আপডেট করা
        db.collection('products').document(prod_id).update({'stock': remaining_stock})
        
        # ইনভয়েস জেনারেট এবং Completed Orders এ সেভ করা
        invoice_id = generate_invoice_id()
        
        db.collection('orders').document(invoice_id).set({
            'order_id': invoice_id, 'invoice_id': invoice_id, 'user_id': user_id, 
            'product_id': prod_id, 'product_name': product['name'],
            'qty': qty, 'total_price': total_price, 'items_delivered': delivered_items, 
            'completed_by': 'System', 'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # 🟢 ইউজারের কাছে অটো-ডেলিভারি মেসেজ পাঠানো (Smart Format)
        delivery_text = (
            f"✅ <b>DELIVERY SUCCESSFUL!</b>\n\n"
            f"🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n"
            f"📦 <b>Package:</b> {product['name']}\n"
            f"🔢 <b>Quantity:</b> {qty}\n"
            f"💰 <b>Total Price:</b> ${total_price}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
        )
        
        for idx, item in enumerate(delivered_items, 1):
            formatted_data = format_delivery_text(cat_name, item)
            delivery_text += f"🛍️ <b>Item {idx}:</b>\n{formatted_data}\n\n"
            
        delivery_text += "➖➖➖➖➖➖➖➖➖➖\n"
        
        buy_again_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛍️ Buy Again", callback_data=f"buyprod_{prod_id}", style="success")]])
        await callback.message.edit_text(delivery_text, reply_markup=buy_again_kb, parse_mode="HTML")
        
        # 🟢 NEW: রিয়েল সেলস অ্যালার্ট গ্রুপে পাঠানো
        await send_real_sales_alert(bot, prod_id, product['name'], user_id)
        
        # স্টক কমে গেলে অ্যাডমিনদের অটোমেটিক অ্যালার্ট দেওয়া
        if len(remaining_stock) <= 2:
            for admin_id in ADMIN_IDS:
                try: await bot.send_message(admin_id, f"⚠️ <b>Low Stock Alert!</b>\nProduct: {product['name']} has only {len(remaining_stock)} left in stock.")
                except: pass
                
    # 🟠 MANUAL LOGIC OR OUT OF STOCK (পেন্ডিং অর্ডারে পাঠানো)
    else:
        # পেন্ডিং অর্ডার তৈরি এবং ইনভয়েস আইডি কালেক্ট করা
        invoice_id = await create_pending_order(user_id, prod_id, product['name'], qty, total_price, delivery_type="manual")
        new_balance = round(user_balance - total_price, 2)
        
        text = (
            f"⏳ <b>Order Processing...</b>\n\n"
            f"🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n"
            f"📦 <b>Product:</b> {product['name']}\n"
            f"🔢 <b>Quantity:</b> {qty}\n"
            f"💰 <b>Total Paid:</b> ${total_price}\n"
            f"💎 <b>Remaining Balance:</b> ${new_balance:.2f}\n\n"
            "👨‍💻 <i>Your order has been sent to the admin. You will receive your details shortly.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", icon_custom_emoji_id=EMOJI_SEARCH)],
            [InlineKeyboardButton(text="🏠 Back to Shop", callback_data="menu_buy", style="primary")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        # অ্যাডমিনদের কাছে নোটিফিকেশন পাঠানো
        admin_text = (
            f"🚨 <b>NEW MANUAL ORDER!</b>\n\n"
            f"🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📦 <b>Product:</b> {product['name']} (x{qty})\n"
            f"💰 <b>Paid:</b> ${total_price}"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Deliver Now", callback_data=f"vieword_{invoice_id}", style="success", icon_custom_emoji_id=EMOJI_DONE)]])
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
            except: pass
