# main.py
import asyncio 
import random
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramServerError, TelegramNetworkError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton 
from firebase_admin import firestore

from config import BOT_TOKEN, MAIN_GROUPS_ID, BOT_USERNAME
from middlewares.force_join import ForceSubMiddleware
from middlewares.maintenance import MaintenanceMiddleware

from database.crud import db, get_bot_status 

# সবগুলো রাউটার ইমপোর্ট করা হচ্ছে
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.payment import router as payment_router
from handlers.wallet import router as wallet_router
from handlers.admin import router as admin_router
from handlers.profile import router as profile_router 
from handlers.others import router as others_router 

# ==========================================
# 🟢 হেল্পার ফাংশন: ফেক সেল মেসেজ (কোয়ান্টিটি সহ)
# ==========================================
async def send_fake_sale_message(bot: Bot, product: dict):
    product_name = product.get('name', 'Premium Service')
    product_id = product.get('product_id', '') 
    
    # র‍্যান্ডম ফেক ইউজার আইডি তৈরি (e.g., 105***78)
    fake_user_id = f"{random.randint(100, 999)}***{random.randint(10, 99)}"
    
    # র‍্যান্ডম কোয়ান্টিটি (বেশিরভাগ সময় 1, মাঝে মাঝে 2, 3 বা 5)
    fake_qty = random.choices([1, 2, 3, 5], weights=[75, 15, 7, 3])[0]
    
    promo_text = (
        f"🎉 <b>New Order Placed!</b>\n\n"
        f"👤 User <code>{fake_user_id}</code> just purchased:\n"
        f"🛍️ <b>{product_name}</b>\n"
        f"🔢 <b>Quantity:</b> {fake_qty}\n\n"
        f"⚡️ <i>Delivered automatically in seconds.</i>"
    )
    
    buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
    buy_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]
    ])
    
    try:
        await bot.send_message(
            chat_id=MAIN_GROUPS_ID,
            text=promo_text,
            parse_mode="HTML",
            reply_markup=buy_btn
        )
    except Exception:
        pass

# ==========================================
# 🟢 NEW: Simulated Sales Loop (Promo Mute & Low Stock Safety Added)
# ==========================================
async def simulated_sales_loop(bot: Bot):
    print("🚀 Simulated Sales Loop Started...")
    await asyncio.sleep(60) 
    
    while True:
        try:
            # মেইনটেনেন্স মোড চেক করা
            is_maintenance = await get_bot_status()
            if is_maintenance:
                await asyncio.sleep(60)
                continue

            if not db or not MAIN_GROUPS_ID:
                await asyncio.sleep(60)
                continue
                
            # ডাটাবেস থেকে অ্যাক্টিভ প্রোডাক্ট নিয়ে আসা
            docs = db.collection('products').stream()
            active_products = []
            
            for doc in docs:
                p_data = doc.to_dict()
                
                # 🟢 NEW: Promo Muted থাকলে ইগনোর করবে
                if p_data.get('status', 'active') == 'active' and not p_data.get('promo_muted', False):
                    
                    # 🟢 NEW: Auto Delivery এর ক্ষেত্রে স্টক ৫ টার কম থাকলে Burst/Promo অফ থাকবে
                    if p_data.get('delivery_type') == 'auto':
                        stock_len = len(p_data.get('stock', []))
                        if stock_len < 5:
                            continue # এই প্রোডাক্টটা প্রমোশনের জন্য নেবে না
                            
                    active_products.append(p_data)
            
            if not active_products:
                await asyncio.sleep(600) 
                continue
                
            # 15% চান্স থাকবে Burst (ঝড়) ট্রিগার হওয়ার
            is_burst_mode = random.random() < 0.15 
            
            if is_burst_mode:
                burst_product = None
                try:
                    # ডাটাবেস থেকে লাস্ট রিয়েল অর্ডারগুলো চেক করা
                    recent_docs = db.collection('orders').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()
                    recent_products = []
                    for doc in recent_docs:
                        d = doc.to_dict()
                        if d.get('product_id'):
                            # চেক করবো যে এই প্রোডাক্টটা আমাদের active_products লিস্টে আছে কি না
                            if any(p['product_id'] == d['product_id'] for p in active_products):
                                recent_products.append({'product_id': d['product_id'], 'name': d.get('product_name')})
                    
                    if recent_products:
                        burst_product = random.choice(recent_products) 
                except Exception:
                    pass
                
                # যদি কোনো রিয়েল সেল না পাওয়া যায়, তখন র‍্যান্ডম প্রোডাক্ট নেবে
                if not burst_product:
                    burst_product = random.choice(active_products)
                    
                burst_count = random.randint(4, 7)
                print(f"🔥 REAL TRENDING BURST! {burst_count} fake sales for {burst_product.get('name')}")
                
                for _ in range(burst_count):
                    # Safety Check: বার্স্ট চলাকালীন যদি হঠাৎ মেইনটেনেন্স অন করা হয়!
                    if await get_bot_status():
                        break 

                    await send_fake_sale_message(bot, burst_product)
                    await asyncio.sleep(random.randint(30, 120))
                
                await asyncio.sleep(random.randint(1800, 3600))
                
            else:
                # 🚶‍♂️ Normal Mode
                random_product = random.choice(active_products)
                await send_fake_sale_message(bot, random_product)
                await asyncio.sleep(random.randint(1800, 3600))
                
        except Exception as e:
            print(f"Simulated Loop Error: {e}")
            await asyncio.sleep(60)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # মিডলওয়্যার যুক্ত করা
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(ForceSubMiddleware())
    dp.callback_query.middleware(ForceSubMiddleware())

    # সব রাউটার ডিসপ্যাচারে যুক্ত করা
    dp.include_router(start_router)
    dp.include_router(shop_router)
    dp.include_router(payment_router)
    dp.include_router(wallet_router)
    dp.include_router(profile_router)
    dp.include_router(others_router)
    dp.include_router(admin_router)

    print("✅ বট সফলভাবে চালু হয়েছে!")
    print("🛡️ Server Crash Protection Activated.")

    # ফেক সেলস ব্যাকগ্রাউন্ড লুপ চালু করা
    asyncio.create_task(simulated_sales_loop(bot))

    while True:
        try:
            await dp.start_polling(bot)
        except (TelegramServerError, TelegramNetworkError) as e:
            print(f"\n⚠️ Telegram Server Error: {e}")
            print("⏳ 5 সেকেন্ড পর আবার কানেক্ট করার চেষ্টা করা হচ্ছে...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"\n❌ Unexpected Error: {e}")
            print("⏳ 10 সেকেন্ড পর আবার কানেক্ট করার চেষ্টা করা হচ্ছে...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    # ফেক ওয়েব সার্ভার চালু করার ম্যাজিক কোড
    ##keep_alive() 
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 বট ম্যানুয়ালি বন্ধ করা হয়েছে।")
