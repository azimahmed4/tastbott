# ==========================================
# File: handlers/payment.py
# Purpose: ইউজারের পেমেন্ট কনফার্মেশন, ব্যালেন্স কাটা, অটো/ম্যানুয়াল ডেলিভারি এবং ইনভয়েস তৈরি
# ==========================================
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from firebase_admin import firestore
from database.crud import db, get_user, get_product, create_pending_order, generate_invoice_id

from config import ADMIN_IDS, BOT_USERNAME, MAIN_GROUPS_ID 

router = Router()

EMOJI_CART = "5368324170671202286"
EMOJI_DONE = "5368324170671202287"
EMOJI_SEARCH = "5368324170671202289"

def format_delivery_text(category: str, raw_data: str) -> str:
    cat = category.lower()
    parts = raw_data.split(":")
    
    if cat == "proxy" and len(parts) >= 4:
        return f"🌐 <b>IP:</b> <code>{parts[0].strip()}</code>\n🔌 <b>Port:</b> <code>{parts[1].strip()}</code>\n👤 <b>User:</b> <code>{parts[2].strip()}</code>\n🔑 <b>Pass:</b> <code>{':'.join(parts[3:]).strip()}</code>"
    elif cat == "vpn" and len(parts) >= 2:
        return f"📧 <b>Mail:</b> <code>{parts[0].strip()}</code>\n🔐 <b>Pass:</b> <code>{':'.join(parts[1:]).strip()}</code>"
    else:
        return f"🔗 <b>Link/Key:</b> <code>{raw_data}</code>"

async def send_real_sales_alert(bot: Bot, product_id: str, product_name: str, user_id: int, qty: int):
    if not MAIN_GROUPS_ID: return
    try:
        str_uid = str(user_id)
        masked_uid = f"{str_uid[:3]}***{str_uid[-2:]}" if len(str_uid) > 4 else f"{str_uid[:1]}***{str_uid[-1:]}"
        promo_text = f"🎉 <b>New Order Placed!</b>\n\n👤 User <code>{masked_uid}</code> just purchased:\n🛍️ <b>{product_name}</b>\n🔢 <b>Quantity:</b> {qty}\n\n⚡️ <i>Delivered automatically in seconds.</i>"
        buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
        await bot.send_message(chat_id=MAIN_GROUPS_ID, text=promo_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]]))
    except Exception: pass 

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    qty = int(parts[1])
    prod_id = "_".join(parts[2:]) 
    
    if not db: return await callback.answer("❌ Database error!", show_alert=True)

    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Error: Product not found!", show_alert=True)
        
    total_price = round(product['price'] * qty, 2)
    cat_name = product.get('category', 'unknown') 
    
    user_data = await get_user(user_id)
    if not user_data: return await callback.answer("❌ Error: User profile not found!", show_alert=True)
        
    user_balance = float(user_data.get('balance', 0.0))
    if user_balance < total_price: return await callback.answer(f"❌ Insufficient balance! You need ${total_price}, but have ${user_balance:.2f}.", show_alert=True)

    db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(-total_price), 'total_spent': firestore.Increment(total_price)})
    
    delivery_type = product.get('delivery_type', 'manual')
    stock_list = product.get('stock', [])
    
    if delivery_type == "auto" and len(stock_list) >= qty:
        delivered_items = stock_list[:qty]
        remaining_stock = stock_list[qty:]
        
        db.collection('products').document(prod_id).update({'stock': remaining_stock})
        invoice_id = generate_invoice_id()
        db.collection('orders').document(invoice_id).set({
            'order_id': invoice_id, 'invoice_id': invoice_id, 'user_id': user_id, 
            'product_id': prod_id, 'product_name': product['name'], 'qty': qty, 'total_price': total_price, 
            'items_delivered': delivered_items, 'completed_by': 'System', 'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        delivery_text = f"✅ <b>DELIVERY SUCCESSFUL!</b>\n\n🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n📦 <b>Package:</b> {product['name']}\n🔢 <b>Quantity:</b> {qty}\n💰 <b>Total Price:</b> ${total_price}\n➖➖➖➖➖➖➖➖➖➖\n"
        for idx, item in enumerate(delivered_items, 1): delivery_text += f"🛍️ <b>Item {idx}:</b>\n{format_delivery_text(cat_name, item)}\n\n"
        delivery_text += "➖➖➖➖➖➖➖➖➖➖\n"
        
        await callback.message.edit_text(delivery_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛍️ Buy Again", callback_data=f"buyprod_{prod_id}", style="success")]]), parse_mode="HTML")
        await send_real_sales_alert(bot, prod_id, product['name'], user_id, qty)
        
        if len(remaining_stock) <= 2:
            alert_text = f"🚨 <b>OUT OF STOCK ALERT!</b>\nProduct: <b>{product['name']}</b> has reached 0 stock.\nPlease add more stock or deliver manually if orders arrive." if len(remaining_stock) == 0 else f"⚠️ <b>Low Stock Alert!</b>\nProduct: <b>{product['name']}</b> has only {len(remaining_stock)} left in stock."
            for admin_id in ADMIN_IDS:
                try: await bot.send_message(admin_id, alert_text, parse_mode="HTML")
                except: pass
                
    else:
        invoice_id = await create_pending_order(user_id, prod_id, product['name'], qty, total_price, delivery_type="manual")
        new_balance = round(user_balance - total_price, 2)
        
        text = (f"⏳ <b>Order Processing...</b>\n\n🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n📦 <b>Product:</b> {product['name']}\n"
                f"🔢 <b>Quantity:</b> {qty}\n💰 <b>Total Paid:</b> ${total_price}\n💎 <b>Remaining Balance:</b> ${new_balance:.2f}\n\n👨‍💻 <i>Your order has been sent to the admin. You will receive your details shortly.</i>")
        
        # 🟢 Show pending message
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", icon_custom_emoji_id=EMOJI_SEARCH)]]), parse_mode="HTML")
        
        # Admin Alert
        admin_text = f"🚨 <b>NEW MANUAL ORDER!</b>\n\n🧾 <b>Invoice:</b> <code>{invoice_id}</code>\n👤 <b>User ID:</b> <code>{user_id}</code>\n📦 <b>Product:</b> {product['name']} (x{qty})\n💰 <b>Paid:</b> ${total_price}"
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Deliver Now", callback_data=f"vieword_{invoice_id}", style="success", icon_custom_emoji_id=EMOJI_DONE)]]), parse_mode="HTML")
            except: pass

        # 🟢 AUTO-REDIRECT TO SHOP MENU (After a short delay to let them read the pending message)
        await asyncio.sleep(1.5)
        shop_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn", style="primary"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy", style="primary")],
            [InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub", style="primary"), InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai", style="primary")],
            [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders|0", style="primary"), InlineKeyboardButton(text="🔍 Track Invoice", callback_data="search_invoice", style="primary")],
            [InlineKeyboardButton(text="📡 All Proxy Checker", callback_data="check_proxy", style="success")],
            [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main", style="danger")]
        ])
        try: await bot.send_message(chat_id=user_id, text="🛒 <b>Shop Categories</b>\n\nPlease select a category:", reply_markup=shop_keyboard, parse_mode="HTML")
        except: pass
