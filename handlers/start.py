from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from firebase_admin import firestore

from middlewares.force_join import check_membership
from keyboards.inline_menus import get_main_menu
from database.crud import db, add_user, get_user
from config import REFERRAL_BONUS

# 🟢 NEW: সরাসরি প্রোডাক্ট কেনার পেজ দেখানোর জন্য shop.py থেকে ফাংশন ইমপোর্ট
from handlers.shop import show_quantity_selector

router = Router()

# 🚀 ফায়ারবেস ব্যবহার করে রেফারেল বোনাস দেওয়ার হেল্পার ফাংশন
async def process_referral_reward(bot: Bot, user_id: int, referrer_id: int):
    # crud.py-এর add_user ফাংশনটি আগেই ইউজারের total_referrals বাড়িয়ে দিয়েছে।
    # এখানে আমরা শুধু রেফারারের ব্যালেন্সে রেফারেল বোনাসটি যোগ করব।
    if not db:
        return

    try:
        referrer_ref = db.collection('users').document(str(referrer_id))
        referrer_doc = referrer_ref.get()
        
        if referrer_doc.exists:
            # রেফারারের ব্যালেন্সে বোনাস যোগ করা
            referrer_ref.update({
                'balance': firestore.Increment(REFERRAL_BONUS)
            })
            
            # টাস্ক কমপ্লিট হলে রেফারারকে নোটিফিকেশন পাঠানো
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
    args = command.args # ?start=123456 OR ?start=buy_p12345
    
    # ফায়ারবেস থেকে চেক করা ইউজার আগে থেকে আছে কি না
    existing_user = await get_user(user_id)
    is_joined = await check_membership(message.bot, user_id)

    # 🟢 NEW: Deep Link Payload Handling (Referral vs Buy Product)
    buy_product_id = None
    referrer_id = None
    
    if args:
        if args.startswith("buy_"):
            buy_product_id = args.split("_", 1)[1] # "buy_p12345" থেকে "p12345" বের করা
        elif args.isdigit():
            ref_id = int(args)
            if ref_id != user_id:
                referrer_id = ref_id

    # যদি নতুন ইউজার হয়
    if not existing_user:
        if is_joined:
            # যদি আগে থেকেই জয়েন থাকে, ফায়ারবেসে সেভ করো (ব্যালেন্স ০ হবে) এবং বোনাস দাও
            is_new = await add_user(user_id, username, first_name, referrer_id)
            if is_new and referrer_id:
                await process_referral_reward(message.bot, user_id, referrer_id)
        else:
            # জয়েন না থাকলে শুধু রেফারারের আইডি ও প্রোডাক্ট আইডি state-এ সেভ করে রাখো
            state_data = {}
            if referrer_id: state_data["referred_by"] = referrer_id
            if buy_product_id: state_data["buy_product_id"] = buy_product_id
            if state_data: await state.update_data(**state_data)

    # যদি ইউজার সব চ্যানেলে জয়েন থাকে, তবেই মেইন মেনু দেখাবে
    if is_joined:
        # 🟢 NEW: যদি ডিপ-লিংক এ buy_ID থাকে, তাহলে সরাসরি প্রোডাক্ট পেজ দেখাও
        if buy_product_id:
            # ফেক কলব্যাক তৈরি করে shop.py এর ফাংশনে পাঠানো হচ্ছে
            fake_callback = CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message)
            
            # আগের মেসেজ ডিলিট করে নতুন মেনু আনার ট্রাই (ক্লিন ইউআই এর জন্য)
            try: await message.delete()
            except: pass
            
            # সরাসরি প্রোডাক্টের পেজ পাঠানো
            sent_msg = await message.answer("⏳ Loading product details...")
            fake_callback.message = sent_msg 
            await show_quantity_selector(fake_callback, buy_product_id, 1)
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
        
        # 🚀 যদি ইউজারের ফায়ারবেস প্রোফাইল না থাকে (অর্থাৎ সে একদম নতুন)
        if not existing_user:
            referrer_id = data.get("referred_by")
            
            # ফায়ারবেসে ইউজার সেভ করা (এখানেই ব্যালেন্স ০ হয়ে যাবে)
            is_new = await add_user(user_id, username, first_name, referrer_id)
            
            # টাস্ক কমপ্লিট, এবার রেফারারকে টাকা দেওয়া হবে
            if is_new and referrer_id:
                await process_referral_reward(bot, user_id, referrer_id)
                
        # 🟢 NEW: নতুন ইউজার জয়েন করার পর যদি ডিপ-লিংক প্রোডাক্ট থাকে, সেটা দেখানো
        buy_product_id = data.get("buy_product_id")
        await state.clear()
        
        if buy_product_id:
            await callback.message.edit_text("⏳ Loading product details...")
            await show_quantity_selector(callback, buy_product_id, 1)
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
