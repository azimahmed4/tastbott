from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from firebase_admin import firestore

from middlewares.force_join import check_membership
from keyboards.inline_menus import get_main_menu
from database.crud import db, add_user, get_user
from config import REFERRAL_BONUS

from handlers.shop import show_quantity_selector

router = Router()

# 🚀 ফায়ারবেস ব্যবহার করে রেফারেল বোনাস দেওয়ার হেল্পার ফাংশন
async def process_referral_reward(bot: Bot, user_id: int, referrer_id: int):
    if not db:
        return

    try:
        referrer_ref = db.collection('users').document(str(referrer_id))
        referrer_doc = referrer_ref.get()
        
        if referrer_doc.exists:
            referrer_ref.update({
                'balance': firestore.Increment(REFERRAL_BONUS)
            })
            
            await bot.send_message(
                chat_id=referrer_id, 
                text=f"🎉 <b>New Referral Success!</b>\nSomeone joined using your link and completed all tasks. You received a bonus of <b>${REFERRAL_BONUS}</b>!",
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"⚠️ Referral reward error: {e}")


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "User"
    args = command.args 
    
    existing_user = await get_user(user_id)
    is_joined = await check_membership(message.bot, user_id)

    buy_product_id = None
    referrer_id = None
    
    if args:
        if args.startswith("buy_"):
            buy_product_id = args.split("_", 1)[1] 
        elif args.isdigit():
            ref_id = int(args)
            if ref_id != user_id:
                referrer_id = ref_id

    if not existing_user:
        if is_joined:
            is_new = await add_user(user_id, username, first_name, referrer_id)
            if is_new and referrer_id:
                await process_referral_reward(message.bot, user_id, referrer_id)
        else:
            state_data = {}
            if referrer_id: state_data["referred_by"] = referrer_id
            if buy_product_id: state_data["buy_product_id"] = buy_product_id
            if state_data: await state.update_data(**state_data)

    if is_joined:
        if buy_product_id:
            try: await message.delete()
            except: pass
            
            # 🟢 FIXED: FakeCallback রিমুভ করে সরাসরি Message পাস করা হয়েছে এবং edit_msg=False করা হয়েছে।
            # এর ফলে চ্যানেল লিংকে ক্লিক করলে আর কোনো গ্লিচি বাটন ছাড়া মেসেজ আসবে না!
            await show_quantity_selector(message, buy_product_id, qty=0, edit_msg=False)
            await state.clear()
            return
            
        await state.clear() 
        welcome_text = f"Welcome to OmniSub Store ! 🚀\nHello {first_name}, please select an option below:"
        await message.answer(welcome_text, reply_markup=get_main_menu())


@router.callback_query(F.data == "check_join")
async def verify_join(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or "User"
    
    is_joined = await check_membership(bot, user_id)
    
    if is_joined:
        existing_user = await get_user(user_id)
        data = await state.get_data()
        
        if not existing_user:
            referrer_id = data.get("referred_by")
            is_new = await add_user(user_id, username, first_name, referrer_id)
            
            if is_new and referrer_id:
                await process_referral_reward(bot, user_id, referrer_id)
                
        buy_product_id = data.get("buy_product_id")
        await state.clear()
        
        if buy_product_id:
            # 🟢 FIXED: নতুন ইউজার চ্যানেল থেকে লিংকে ক্লিক করে জয়েন করার পর ডিরেক্ট কলব্যাক কাজ করবে
            await show_quantity_selector(callback, buy_product_id, qty=0, edit_msg=True)
            return
            
        welcome_text = f"Welcome to OmniSub Store! 🚀\nHello {first_name}, please select an option below:"
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
    else:
        await callback.answer("❌ You haven't joined all channels/groups yet! Please join first.", show_alert=True)


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome_text = f"Welcome to OmniSub Store! 🚀\nHello {callback.from_user.first_name}, please select an option below:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
