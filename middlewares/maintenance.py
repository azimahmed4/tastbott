# ==========================================
# File: middlewares/maintenance.py
# Purpose: মেইনটেনেন্স মোড অন থাকলে ইউজারদের ব্লক করা
# ==========================================
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from database.crud import get_bot_status
from config import ADMIN_IDS

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        # 🚀 অ্যাডমিনদের জন্য সব সময় বট খোলা থাকবে (যাতে তারা টেস্ট করতে পারে)
        if user_id in ADMIN_IDS:
            return await handler(event, data)
            
        # 🔒 সাধারণ ইউজারের জন্য মেইনটেনেন্স চেক
        is_maintenance = await get_bot_status()
        if is_maintenance:
            text = "🛠️ <b>System Maintenance</b>\n\nবটটি বর্তমানে আপডেটের কাজের জন্য সাময়িক বন্ধ আছে। দয়া করে কিছুক্ষণ পর আবার চেষ্টা করুন।"
            
            if isinstance(event, Message):
                await event.answer(text, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("🛠️ Bot is under maintenance!", show_alert=True)
                
            # ❌ রিটার্ন করে দেওয়া হলো, অর্থাৎ ইউজারের রিকোয়েস্ট আর সামনের দিকে (handlers-এ) যাবে না
            return 
            
        # ✅ বট লাইভ থাকলে নরমালি কাজ করবে
        return await handler(event, data)
