# ==========================================
# File: middlewares/force_join.py
# Purpose: ফোর্স সাবস্ক্রাইব / চ্যানেল জয়েন চেক করা
# ==========================================
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest

from config import REQUIRED_CHANNELS
from keyboards.inline_menus import get_join_menu

async def check_membership(bot: Bot, user_id: int) -> bool:
    for chat in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except TelegramBadRequest:
            # যদি বট চ্যানেলে অ্যাডমিন না থাকে বা অন্য কোনো API এরর আসে
            return False
    return True

class ForceSubMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        # 🚀 Verify বাটনে ক্লিক করলে মিডলওয়্যার বাইপাস করে start.py তে পাঠাবে
        if isinstance(event, CallbackQuery) and event.data == "check_join":
            return await handler(event, data)

        bot: Bot = data.get("bot")
        is_joined = await check_membership(bot, user.id)
        
        if not is_joined:
            join_text = (
                "⚠️ <b>Access Denied!</b>\n\n"
                "You must join our official channels and group to continue using this bot. "
                "Click the buttons below to join, then click <b>Verify</b>."
            )
            
            if isinstance(event, Message):
                await event.answer(join_text, reply_markup=get_join_menu(), parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(join_text, reply_markup=get_join_menu(), parse_mode="HTML")
                await event.answer()
            return # ❌ ইউজারকে আটকে দেওয়া হলো
        
        # ✅ জয়েন থাকলে লজিক সামনের দিকে যাবে
        return await handler(event, data)
