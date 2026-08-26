# middlewares/force_join.py
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
        
        if isinstance(event, CallbackQuery) and event.data == "check_join":
            return await handler(event, data)

        bot: Bot = data.get("bot")
        is_joined = await check_membership(bot, user.id)
        
        if not is_joined:
            join_text = "⚠️ <b>Access Denied!</b>\n\nYou must join our official channels and group to continue using this bot. Click the buttons below to join, then click <b>Verify</b>."
            
            if isinstance(event, Message):
                await event.answer(join_text, reply_markup=get_join_menu(), parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(join_text, reply_markup=get_join_menu(), parse_mode="HTML")
                await event.answer()
            return
        
        return await handler(event, data)