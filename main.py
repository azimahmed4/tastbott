# main.py
import asyncio 
import random
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramServerError, TelegramNetworkError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton # 🟢 NEW: বাটনের জন্য ইমপোর্ট

from config import BOT_TOKEN, MAIN_GROUPS_ID, BOT_USERNAME
from middlewares.force_join import ForceSubMiddleware
from middlewares.maintenance import MaintenanceMiddleware

from database.crud import db 

# সবগুলো রাউটার ইমপোর্ট করা হচ্ছে
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.payment import router as payment_router
from handlers.wallet import router as wallet_router
from handlers.admin import router as admin_router
from handlers.profile import router as profile_router 
from handlers.others import router as others_router 

# ==========================================
# 🟢 NEW: Simulated Sales Loop (FOMO Marketing)
# ==========================================
async def simulated_sales_loop(bot: Bot):
    print("🚀 Simulated Sales Loop Started...")
    await asyncio.sleep(60) # বট চালুর 1 মিনিট পর থেকে হিসাব শুরু
    
    while True:
        # 30 মিনিট (1800 সেকেন্ড) থেকে 90 মিনিট (5400 সেকেন্ড) এর মধ্যে র‍্যান্ডম সময়
        sleep_interval = random.randint(20, 40) 
        await asyncio.sleep(sleep_interval)
        
        try:
            if not db or not MAIN_GROUPS_ID:
                continue
                
            # ডাটাবেস থেকে সব প্রোডাক্ট নিয়ে আসা
            docs = db.collection('products').stream()
            products = [doc.to_dict() for doc in docs]
            
            if not products:
                continue
                
            # একটি র‍্যান্ডম প্রোডাক্ট বেছে নেওয়া
            random_product = random.choice(products)
            product_name = random_product.get('name', 'Premium Service')
            product_id = random_product.get('product_id', '') # প্রোডাক্ট আইডি
            
            # র‍্যান্ডম ফেক ইউজার আইডি তৈরি (e.g., 105***78)
            fake_user_id = f"{random.randint(100, 999)}***{random.randint(10, 99)}"
            
            # গ্রুপে পাঠানোর জন্য সুন্দর মেসেজ (ইউজারনেম টেক্সট রিমুভ করা হয়েছে)
            promo_text = (
                f"🎉 <b>New Order Placed!</b>\n\n"
                f"👤 User <code>{fake_user_id}</code> just purchased:\n"
                f"🛍️ <b>{product_name}</b>\n\n"
                f"⚡️ <i>Delivered automatically in seconds.</i>"
            )
            
            # 🟢 NEW: Buy Now Button (সরাসরি ওই প্রোডাক্ট কেনার লিংক)
            buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
            buy_btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]
            ])
            
            # গ্রুপে মেসেজ সেন্ড করা
            await bot.send_message(
                chat_id=MAIN_CHANNEL_ID,
                text=promo_text,
                parse_mode="HTML",
                reply_markup=buy_btn
            )
        except Exception as e:
            pass

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

    # 🟢 NEW: ফেক সেলস ব্যাকগ্রাউন্ড লুপ চালু করা
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
