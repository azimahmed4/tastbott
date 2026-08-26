# main.py
import asyncio 
from keep_alive import keep_alive
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramServerError, TelegramNetworkError
from config import BOT_TOKEN
from middlewares.force_join import ForceSubMiddleware

# সবগুলো রাউটার ইমপোর্ট করা হচ্ছে
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.payment import router as payment_router
from handlers.wallet import router as wallet_router
from handlers.admin import router as admin_router
from handlers.profile import router as profile_router 
from handlers.others import router as others_router # How to use, Support, Refer এখানে আছে

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # মিডলওয়্যার যুক্ত করা
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
    # ফেক ওয়েব সার্ভার চালু করার ম্যাজিক কোড
    keep_alive() 
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 বট ম্যানুয়ালি বন্ধ করা হয়েছে।")