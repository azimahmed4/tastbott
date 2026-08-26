# handlers/start.py
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from middlewares.force_join import check_membership
from keyboards.inline_menus import get_main_menu
from database.dummy_db import USER_BALANCES, REFERRED_BY, USER_REFERRALS
from config import REFERRAL_BONUS

router = Router()

# 🚀 রেফারেল বোনাস দেওয়ার জন্য নতুন হেল্পার ফাংশন
async def process_referral_reward(bot: Bot, user_id: int, referrer_id: int):
    # ইউজারের ব্যালেন্স অলরেডি থাকলে সে পুরোনো ইউজার, বোনাস দেওয়া হবে না
    if user_id in USER_BALANCES:
        return
        
    REFERRED_BY[user_id] = referrer_id
    USER_REFERRALS[referrer_id] = USER_REFERRALS.get(referrer_id, 0) + 1
    USER_BALANCES[referrer_id] = round(USER_BALANCES.get(referrer_id, 0.0) + REFERRAL_BONUS, 2)
    
    # টাস্ক কমপ্লিট হলে রেফারারকে নোটিফিকেশন পাঠানো
    try:
        await bot.send_message(
            chat_id=referrer_id, 
            text=f"🎉 <b>New Referral Success!</b>\nSomeone joined using your link and completed all tasks. You received a bonus of <b>${REFERRAL_BONUS}</b>!",
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear() 
    user_id = message.from_user.id
    args = command.args # ?start=123456
    
    is_joined = await check_membership(message.bot, user_id)

    # 🚀 নতুন ইউজারের রেফারেল ট্র্যাকিং (কিন্তু টাকা সাথে সাথে দেওয়া হবে না)
    if user_id not in USER_BALANCES:
        if args and args.isdigit():
            referrer_id = int(args)
            # নিজে নিজেকে রেফার না করলে এবং আগে অন্য কারো রেফারে না থাকলে
            if referrer_id != user_id and user_id not in REFERRED_BY:
                if is_joined:
                    # যদি আগে থেকেই জয়েন থাকে (বা ফোর্স জয়েন অফ থাকে), সাথে সাথে বোনাস
                    await process_referral_reward(message.bot, user_id, referrer_id)
                else:
                    # জয়েন না থাকলে শুধু রেফারারের আইডি সেভ করে রাখো, Check Join-এ টাকা পাবে
                    REFERRED_BY[user_id] = referrer_id

    # যদি ইউজার সব চ্যানেলে জয়েন থাকে, তবেই তাকে নতুন ইউজারের ডিফল্ট ব্যালেন্স দাও
    if is_joined and user_id not in USER_BALANCES:
        USER_BALANCES[user_id] = 20.0
        
    welcome_text = f"Welcome to AIVerse X Hub! 🚀\nHello {message.from_user.first_name}, please select an option below:"
    await message.answer(welcome_text, reply_markup=get_main_menu())

@router.callback_query(F.data == "check_join")
async def verify_join(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_joined = await check_membership(bot, user_id)
    
    if is_joined:
        # 🚀 যদি ইউজারের রেফারেল পেন্ডিং থাকে এবং সে নতুন ইউজার হয়
        if user_id not in USER_BALANCES:
            referrer_id = REFERRED_BY.get(user_id)
            if referrer_id:
                # টাস্ক কমপ্লিট, এবার রেফারারকে টাকা দেওয়া হবে
                await process_referral_reward(bot, user_id, referrer_id)
                
            # টাস্ক কমপ্লিট করার পর নতুন ইউজারের ডিফল্ট ব্যালেন্স সেট করা
            USER_BALANCES[user_id] = 20.0
            
        welcome_text = f"Welcome to AIVerse X Hub! 🚀\nHello {callback.from_user.first_name}, please select an option below:"
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
    else:
        await callback.answer("❌ You haven't joined all channels/groups yet! Please join first.", show_alert=True)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome_text = f"Welcome to AIVerse X Hub! 🚀\nHello {callback.from_user.first_name}, please select an option below:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())