# ==========================================
# File: handlers/admin.py
# Purpose: বটের অ্যাডমিন প্যানেল, ডেলিভারি, প্রোডাক্ট ম্যানেজমেন্ট এবং প্রাইস লিস্ট
# ==========================================
import time
import asyncio
from datetime import datetime, timedelta, timezone, time as dt_time
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from firebase_admin import firestore

from config import ADMIN_IDS, MAIN_CHANNEL_ID, MAIN_GROUPS_ID, BOT_USERNAME
from database.crud import (db, get_product, delete_product, add_subcategory, get_subcategories, 
                           delete_subcategory, get_products_by_category, save_deposit_history, 
                           get_deposit_statement, set_bot_status, get_bot_status,
                           get_all_payment_methods, update_payment_method)

router = Router()

EMOJI_SETTINGS = "5368324170671202286"
EMOJI_BOX = "5368324170671202287"
EMOJI_MONEY = "5368324170671202288"
EMOJI_USER = "5368324170671202289"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def get_autopost_status():
    if not db: return True
    doc = db.collection('settings').document('autopost').get()
    if doc.exists:
        return doc.to_dict().get('is_active', True)
    return True

async def set_autopost_status(status: bool):
    if not db: return False
    db.collection('settings').document('autopost').set({'is_active': status}, merge=True)
    return True

async def get_admin_menu():
    is_maintenance = await get_bot_status()
    m_text = "🛠️ Turn Maintenance OFF" if is_maintenance else "⚙️ Turn Maintenance ON"
    m_style = "danger" if is_maintenance else "primary"
    
    is_autopost = await get_autopost_status()
    ap_text = "🔕 Channel Post: OFF" if not is_autopost else "🔔 Channel Post: ON"
    ap_style = "danger" if not is_autopost else "success"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Pending Deposits", callback_data="admin_deposits", style="primary", icon_custom_emoji_id=EMOJI_MONEY), InlineKeyboardButton(text="📦 Pending Orders", callback_data="admin_orders", style="primary", icon_custom_emoji_id=EMOJI_BOX)],
        [InlineKeyboardButton(text="🛒 Manage Products", callback_data="admin_products", style="primary"), InlineKeyboardButton(text="👥 Users", callback_data="admin_users", style="primary", icon_custom_emoji_id=EMOJI_USER)],
        [InlineKeyboardButton(text="📋 Price List", callback_data="admin_price_list", style="primary"), InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast", style="primary")],
        [InlineKeyboardButton(text="📅 Today's Deposits", callback_data="admin_today_deposits", style="primary"), InlineKeyboardButton(text="📦 Today's Orders", callback_data="admin_recent_orders", style="primary")],
        [InlineKeyboardButton(text="⚙️ Payment Settings", callback_data="admin_payment_settings", style="primary", icon_custom_emoji_id=EMOJI_SETTINGS), InlineKeyboardButton(text="📊 Total Deposit Report", callback_data="admin_report", style="primary")],
        [InlineKeyboardButton(text=m_text, callback_data="toggle_maintenance", style=m_style), InlineKeyboardButton(text=ap_text, callback_data="toggle_autopost", style=ap_style)],
        [InlineKeyboardButton(text="❌ Close Panel", callback_data="close_admin", style="danger")]
    ])

class AddSubCatState(StatesGroup):
    category = State()
    name = State()

class AddProductState(StatesGroup):
    category = State()
    sub_category = State()
    name = State()
    price = State()
    description = State()

class EditProductState(StatesGroup):
    waiting_for_price = State()
    waiting_for_stock = State()
    waiting_for_desc = State() 
    waiting_for_minqty = State() # 🟢 NEW STATE FOR MOQ
    product_id = State()
    old_price = State()
    prod_name = State()

class DeliveryState(StatesGroup):
    waiting_for_key = State()
    order_id = State()
    prompt_msg_id = State()
    current_item_num = State()
    total_qty = State()
    delivered_items = State()

class UserManageState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    action_type = None 
    target_user = None

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_button = State()
    waiting_for_destination = State() 
    product_btn_id = State()
    waiting_for_custom_btn = State() 

class PaymentSettingState(StatesGroup):
    waiting_for_new_value = State()
    method_key = State()
    method_data = State()
    edit_type = State() 

@router.message(Command("admin"))
async def show_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id): return 
    menu = await get_admin_menu()
    await message.answer("👨‍💻 <b>Admin Control Panel</b>\n\nSelect an action below:", reply_markup=menu, parse_mode="HTML")

@router.callback_query(F.data == "close_admin")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if is_admin(callback.from_user.id): 
        await callback.message.delete()

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if is_admin(callback.from_user.id):
        menu = await get_admin_menu()
        try:
            await callback.message.edit_text("👨‍💻 <b>Admin Control Panel</b>", reply_markup=menu, parse_mode="HTML")
        except:
            await callback.message.delete()
            await callback.message.answer("👨‍💻 <b>Admin Control Panel</b>", reply_markup=menu, parse_mode="HTML")

# --- Maintenance & Payment functions remain same... ---
@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance_mode(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    current_status = await get_bot_status()
    new_status = not current_status
    await set_bot_status(new_status)
    status_text = "ON" if new_status else "OFF (Live)"
    await callback.answer(f"Maintenance Mode is now {status_text}!", show_alert=True)
    menu = await get_admin_menu()
    await callback.message.edit_reply_markup(reply_markup=menu)
    if MAIN_CHANNEL_ID:
        try:
            if new_status:
                await bot.send_message(MAIN_CHANNEL_ID, "🛠️ <b>System Update Notice</b>\n\nOur bot is currently undergoing maintenance and upgrades. Please wait patiently. We will be back soon!", parse_mode="HTML")
            else:
                await bot.send_message(MAIN_CHANNEL_ID, "✅ <b>System is Live!</b>\n\nThe maintenance is complete and the bot is fully operational now. Thank you for your patience!", parse_mode="HTML")
        except Exception: pass
    if not new_status and db:
        asyncio.create_task(broadcast_live_status(bot))

async def broadcast_live_status(bot: Bot):
    users = [doc.id for doc in db.collection('users').stream()]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Start Bot", url=f"https://t.me/{BOT_USERNAME}", style="primary")], [InlineKeyboardButton(text="🛒 Shop Now", callback_data="menu_buy", style="primary")]])
    for uid in users:
        try: await bot.send_message(chat_id=int(uid), text="🎉 <b>Great News!</b>\n\nOur bot is completely upgraded and fully <b>LIVE</b> right now! You can continue using our services.", reply_markup=keyboard, parse_mode="HTML")
        except: pass

@router.callback_query(F.data == "toggle_autopost")
async def toggle_autopost_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    current_status = await get_autopost_status()
    new_status = not current_status
    await set_autopost_status(new_status)
    await callback.answer(f"Channel Auto-Post is now {'ON' if new_status else 'OFF'}")
    menu = await get_admin_menu()
    await callback.message.edit_reply_markup(reply_markup=menu)

@router.callback_query(F.data == "admin_payment_settings")
async def show_payment_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    methods = await get_all_payment_methods()
    keyboard = []
    for key, data in methods.items():
        status_emoji = "✅" if data.get('is_active', True) else "❌"
        display_val = data.get('number', 'N/A') if data.get('type') == 'local' else data.get('pay_id') or data.get('address') or 'N/A'
        if len(display_val) > 15: display_val = display_val[:6] + "..." + display_val[-4:]
        btn_text = f"{status_emoji} {data['name']} | {display_val}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"payset_edit|{key}", style="primary")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")])
    await callback.message.edit_text("⚙️ <b>Payment Settings</b>\n\nClick on a payment method to turn it ON/OFF or edit its details.", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("payset_edit|"))
async def edit_single_payment_setting(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split("|")[1]
    methods = await get_all_payment_methods()
    data = methods.get(key)
    if not data: return await callback.answer("❌ Error loading payment method.", show_alert=True)
    status = "ON (Active)" if data.get('is_active', True) else "OFF (Disabled)"
    toggle_text = "🔴 Turn OFF" if data.get('is_active', True) else "🟢 Turn ON"
    toggle_style = "danger" if data.get('is_active', True) else "success"
    keyboard_layout = [[InlineKeyboardButton(text=toggle_text, callback_data=f"payset_toggle|{key}", style=toggle_style)]]
    if data.get('type') == 'local':
        val_label, current_val = "Number", data.get('number', 'N/A')
        keyboard_layout.append([InlineKeyboardButton(text=f"✏️ Edit {val_label}", callback_data=f"payset_changeval|{key}", style="primary")])
    else:
        val_label, current_val = "Address/Pay ID", data.get('pay_id') or data.get('address') or 'N/A'
    keyboard_layout.append([InlineKeyboardButton(text="◀️ Back to Settings", callback_data="admin_payment_settings", style="primary")])
    text = f"⚙️ <b>Edit Payment Method:</b> {data['name']}\n\n🔹 <b>Status:</b> {status}\n🔹 <b>Current {val_label}:</b> <code>{current_val}</code>\n\n"
    text += "⚠️ <i>Crypto IDs cannot be edited.</i>" if data.get('type') == 'crypto' else "What do you want to do?"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_layout), parse_mode="HTML")

@router.callback_query(F.data.startswith("payset_toggle|"))
async def toggle_payment_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split("|")[1]
    methods = await get_all_payment_methods()
    data = methods.get(key)
    if data:
        data['is_active'] = not data.get('is_active', True)
        await update_payment_method(key, data)
        await callback.answer(f"✅ Status changed for {data['name']}!")
        callback.data = f"payset_edit|{key}"
        await edit_single_payment_setting(callback)

@router.callback_query(F.data.startswith("payset_changeval|"))
async def prompt_payment_value_change(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.split("|")[1]
    methods = await get_all_payment_methods()
    data = methods.get(key)
    if not data: return
    if data.get('type') != 'local': return await callback.answer("❌ This method cannot be edited.", show_alert=True)
    await state.update_data(method_key=key, method_data=data, edit_type="number")
    await state.set_state(PaymentSettingState.waiting_for_new_value)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"payset_edit|{key}", style="danger")]])
    await callback.message.edit_text(f"✏️ <b>Enter the new Number for {data['name']}:</b>", reply_markup=keyboard, parse_mode="HTML")

@router.message(PaymentSettingState.waiting_for_new_value)
async def save_new_payment_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    new_value = message.text.strip()
    user_data = await state.get_data()
    key, data, edit_type = user_data['method_key'], user_data['method_data'], user_data['edit_type']
    data[edit_type] = new_value
    await update_payment_method(key, data)
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Settings", callback_data="admin_payment_settings", style="primary")]])
    await message.answer(f"✅ Successfully updated {data['name']} {edit_type.title()} to: <code>{new_value}</code>", reply_markup=keyboard, parse_mode="HTML")

# --- Deposit & Reporting ---
@router.callback_query(F.data == "admin_report")
async def show_deposit_report(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer("Generating Report...")
    report_data = await get_deposit_statement()
    if not report_data:
        text = "📊 <b>TOTAL DEPOSIT STATEMENT</b>\n\n⚠️ No deposit history found yet."
    else:
        text = "📊 <b>TOTAL DEPOSIT STATEMENT</b>\n\n"
        total_usd = sum((det['amount'] / 125.0) if det['currency'] == "BDT" else det['amount'] for det in report_data.values())
        for method, details in report_data.items():
            text += f"🔹 <b>{method}:</b> {details['amount']:,.2f} {details['currency']}\n"
        text += f"\n💰 <b>Estimated Total (USD):</b> ~${total_usd:,.2f}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="primary")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_today_deposits")
async def show_today_deposits(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return await callback.answer("Database Error", show_alert=True)
    await callback.answer("Loading today's transactions...")
    bdt_tz = timezone(timedelta(hours=6))
    today_midnight_bdt = datetime.combine(datetime.now(bdt_tz).date(), dt_time.min).replace(tzinfo=bdt_tz)
    docs = db.collection('deposit_history').where('timestamp', '>=', today_midnight_bdt).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    method_counts, trx_list, total_bdt, total_usd = {}, [], 0, 0
    for doc in docs:
        data = doc.to_dict()
        method, amount, currency = data.get('method', 'Unknown'), data.get('amount', 0), data.get('currency', 'BDT')
        method_counts[method] = method_counts.get(method, 0) + 1
        total_bdt += amount if currency == "BDT" else 0
        total_usd += amount if currency != "BDT" else 0
        trx_list.append(f"▪️ <b>{method}:</b> <code>{data.get('trx_id', 'Unknown')}</code> ({amount} {currency})")
    if not trx_list:
        text = "📅 <b>Today's Transactions</b>\n\n⚠️ No approved transactions found for today."
    else:
        text = "📅 <b>Today's Transactions</b>\n\n📊 <b>Summary:</b>\n" + "".join([f"🔹 {m}: {c} pcs\n" for m, c in method_counts.items()])
        text += f"\n💰 <b>Total (BDT):</b> {total_bdt:,.2f} ৳\n💎 <b>Total (USD):</b> ${total_usd:,.2f}\n\n🧾 <b>Recent TrxIDs:</b>\n" + "\n".join(trx_list[:25])
        if len(trx_list) > 25: text += f"\n<i>...and {len(trx_list) - 25} more.</i>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="back_to_admin", style="primary")]]), parse_mode="HTML")

@router.callback_query(F.data == "admin_recent_orders")
async def show_recent_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return await callback.answer("Database Error", show_alert=True)
    await callback.answer("Loading today's orders...")
    bdt_tz = timezone(timedelta(hours=6))
    today_midnight_bdt = datetime.combine(datetime.now(bdt_tz).date(), dt_time.min).replace(tzinfo=bdt_tz)
    docs = db.collection('orders').where('timestamp', '>=', today_midnight_bdt).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    total_sales, total_items, orders_list = 0.0, 0, []
    for doc in docs:
        data = doc.to_dict()
        qty, price = data.get('qty', 1), data.get('total_price', 0.0)
        total_items += qty; total_sales += price
        orders_list.append(f"📦 <b>{data.get('product_name', 'Unknown')}</b> (x{qty}) - ${price}\n   └ 🔖 <b>Trk ID:</b> <code>{data.get('invoice_id', doc.id)}</code>")
    if not orders_list: text = "📦 <b>Today's Orders</b>\n\n⚠️ No orders have been completed today."
    else:
        text = f"📦 <b>Today's Orders</b>\n\n📊 <b>Items Sold:</b> {total_items}\n💰 <b>Total Sales:</b> ${total_sales:.2f}\n\n🧾 <b>Order Details:</b>\n" + "\n".join(orders_list[:25])
        if len(orders_list) > 25: text += f"\n<i>...and {len(orders_list) - 25} more orders.</i>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="back_to_admin", style="primary")]]), parse_mode="HTML")

# --- Price List ---
@router.callback_query(F.data == "admin_price_list")
async def price_list_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="plist_cat_vpn", style="primary"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="plist_cat_proxy", style="primary")],
        [InlineKeyboardButton(text="🎟️ Premium", callback_data="plist_cat_sub", style="primary"), InlineKeyboardButton(text="🤖 AI Service", callback_data="plist_cat_ai", style="primary")],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")]
    ])
    await callback.message.edit_text("📋 <b>Generate Price List</b>\n\nWhich category list do you want to generate?", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("plist_cat_"))
async def price_list_subcat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat = callback.data.split("_")[2]
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        keyboard = [[InlineKeyboardButton(text=f"📂 {sc['name']}", callback_data=f"plist_gen|{cat}|{sc['subcat_id']}", style="primary")] for sc in subcats]
        keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="admin_price_list", style="danger")])
        await callback.message.edit_text("📂 <b>Select Sub-Category:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        await generate_list_message(callback, cat, "none")

@router.callback_query(F.data.startswith("plist_gen|"))
async def price_list_generate_callback(callback: CallbackQuery):
    await generate_list_message(callback, callback.data.split("|")[1], callback.data.split("|")[2])

async def generate_list_message(callback: CallbackQuery, cat: str, subcat: str):
    products_dict = await get_products_by_category(cat, subcat)
    if not products_dict: return await callback.answer("⚠️ No products found!", show_alert=True)
    msg_text = f"🔥 <b>Available {cat.upper()} Packages</b> 🔥\n\n"
    for pid, details in products_dict.items():
        if details.get('status', 'active') == 'active': msg_text += f"✅ {details['name']} ➔ <b>${details['price']}</b>\n"
    msg_text += f"\n🛒 <i>Order now from our bot! @{BOT_USERNAME}</i>"
    await callback.message.delete()
    await callback.message.answer(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Admin Panel", callback_data="back_to_admin", style="danger")]]), parse_mode="HTML")

# --- Deposit Approvals ---
@router.callback_query(F.data == "admin_deposits")
async def show_pending_deposits(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return
    docs = db.collection('pending_deposits').where('status', '==', 'pending').stream()
    keyboard = [[InlineKeyboardButton(text=f"🧾 {doc.id} | {doc.to_dict().get('amount')} BDT", callback_data=f"viewdep_{doc.id}", style="primary")] for doc in docs]
    if not keyboard: return await callback.answer("✅ No pending deposits right now!", show_alert=True)
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")])
    text, markup = "⏳ <b>Pending Deposits:</b>", InlineKeyboardMarkup(inline_keyboard=keyboard)
    try:
        if callback.message.photo or callback.message.document:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")
        else: await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("viewdep_"))
async def view_single_deposit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    trxid = callback.data.split("_")[1]
    doc = db.collection('pending_deposits').document(trxid).get()
    if not doc.exists or doc.to_dict().get('status') != 'pending': return await callback.answer("❌ Already processed.", show_alert=True)
    data = doc.to_dict()
    amount_bdt, amount_usd = data.get('amount', 0), round(data.get('amount', 0) / 125.0, 2) 
    text = (f"🔍 <b>Deposit Request</b>\n\n👤 <b>User ID:</b> <code>{data.get('user_id')}</code>\n🏦 <b>Method:</b> {data.get('method')}\n"
            f"📱 <b>Sender:</b> <code>{data.get('sender_number', 'N/A')}</code>\n💵 <b>Amount:</b> {amount_bdt} BDT (~${amount_usd})\n🧾 <b>TrxID:</b> <code>{data.get('trx_id')}</code>\n")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Approve", callback_data=f"appdep_{trxid}", style="success"), InlineKeyboardButton(text="❌ Reject", callback_data=f"rejdep_{trxid}", style="danger")], [InlineKeyboardButton(text="◀️ Back", callback_data="admin_deposits", style="primary")]])
    try:
        if callback.message.photo or callback.message.document: await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
        else: await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("appdep_"))
async def approve_deposit(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    trxid = callback.data.split("_")[1]
    doc_ref = db.collection('pending_deposits').document(trxid)
    doc = doc_ref.get()
    menu = await get_admin_menu()
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        await callback.answer("❌ Already processed.", show_alert=True)
        await callback.message.delete()
        return await callback.message.answer("👨‍💻 <b>Admin Control Panel</b>\n\nSelect an action below:", reply_markup=menu, parse_mode="HTML")
    data = doc.to_dict()
    user_id, amount_bdt, method_name = data.get('user_id'), data.get('amount', 0), data.get('method', 'Local Payment')
    amount_usd = round(amount_bdt / 125.0, 2)
    db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(amount_usd)})
    doc_ref.update({'status': 'approved'})
    await save_deposit_history(user_id=user_id, amount=amount_bdt, method=method_name, trx_id=trxid, currency="BDT")
    try: await bot.send_message(user_id, f"🎉 <b>Deposit Approved!</b>\n<b>${amount_usd}</b> added to your wallet.", parse_mode="HTML")
    except: pass
    await callback.answer("✅ Deposit Approved!", show_alert=True)
    await callback.message.delete() 
    await callback.message.answer("👨‍💻 <b>Admin Control Panel</b>", reply_markup=menu, parse_mode="HTML")

@router.callback_query(F.data.startswith("rejdep_"))
async def reject_deposit(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    trxid = callback.data.split("_")[1]
    doc_ref = db.collection('pending_deposits').document(trxid)
    doc = doc_ref.get()
    menu = await get_admin_menu()
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        await callback.answer("❌ Already processed.", show_alert=True)
        await callback.message.delete()
        return await callback.message.answer("👨‍💻 <b>Admin Control Panel</b>", reply_markup=menu, parse_mode="HTML")
    data = doc.to_dict()
    user_id, amount_bdt = data.get('user_id'), data.get('amount', 0)
    doc_ref.update({'status': 'rejected'})
    try: await bot.send_message(user_id, f"❌ <b>Deposit Rejected!</b>\nYour request for {amount_bdt} BDT was rejected.", parse_mode="HTML")
    except: pass
    await callback.answer("❌ Deposit Rejected!", show_alert=True)
    await callback.message.delete() 
    await callback.message.answer("👨‍💻 <b>Admin Control Panel</b>", reply_markup=menu, parse_mode="HTML")

# --- Order Delivery ---
@router.callback_query(F.data == "admin_orders")
async def show_pending_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    if not db: return
    docs = db.collection('pending_orders').where('status', '==', 'pending').stream()
    keyboard = [[InlineKeyboardButton(text=f"📦 {doc.to_dict().get('product_name')} (x{doc.to_dict().get('qty')})", callback_data=f"vieword_{doc.to_dict().get('invoice_id', doc.id)}", style="primary")] for doc in docs]
    if not keyboard: return await callback.answer("✅ No pending orders right now!", show_alert=True)
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")])
    await callback.message.edit_text("⏳ <b>Pending Orders:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("vieword_"))
async def view_single_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    doc = db.collection('pending_orders').document(order_id).get()
    if not doc.exists or doc.to_dict().get('status') != 'pending': return await callback.answer("❌ This order was already fulfilled.", show_alert=True)
    data = doc.to_dict()
    text = (f"🛒 <b>Pending Order Details</b>\n\n🧾 <b>Invoice:</b> <code>{data.get('invoice_id', order_id)}</code>\n👤 <b>User ID:</b> <code>{data.get('user_id')}</code>\n"
            f"📦 <b>Product:</b> {data.get('product_name')}\n🔢 <b>Quantity:</b> {data.get('qty')}\n💰 <b>Total Paid:</b> ${data.get('total_price')}\n")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Deliver Now", callback_data=f"deliver_{order_id}", style="success")], [InlineKeyboardButton(text="❌ Refund & Reject", callback_data=f"reford_{order_id}", style="danger")], [InlineKeyboardButton(text="◀️ Back", callback_data="admin_orders", style="primary")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("deliver_"))
async def start_delivery(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    doc = db.collection('pending_orders').document(order_id).get()
    if not doc.exists: return await callback.answer("Error: Order missing.")
    qty = int(doc.to_dict().get('qty', 1))
    prompt = await callback.message.edit_text(f"📝 <b>Delivery Required (Item 1 of {qty})</b>\n\nPlease send details for Item #1 below OR upload a File:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_delivery", style="danger")]]))
    await state.set_state(DeliveryState.waiting_for_key)
    await state.update_data(order_id=order_id, prompt_msg_id=prompt.message_id, current_item_num=1, total_qty=qty, delivered_items=[])

@router.callback_query(F.data == "cancel_delivery")
async def cancel_delivery(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.clear()
    await callback.message.delete()
    await callback.answer("Delivery Cancelled.")

@router.message(DeliveryState.waiting_for_key)
async def process_delivery_key(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    user_data = await state.get_data()
    order_id, prompt_msg_id, current_num, total_qty, delivered_items = user_data['order_id'], user_data['prompt_msg_id'], user_data['current_item_num'], user_data['total_qty'], user_data.get('delivered_items', [])
    doc_ref = db.collection('pending_orders').document(order_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get('status') != 'pending':
        await state.clear()
        return await message.answer("❌ Error: Order not found or already processed.")
    data = doc.to_dict()
    user_id, product_id, product_name = data.get('user_id'), data.get('product_id'), data.get('product_name')
    
    if message.document:
        file_id, file_name = message.document.file_id, message.document.file_name
        delivery_caption = (f"✅ <b>DELIVERY SUCCESSFUL!</b>\n\n🧾 <b>Invoice:</b> <code>{data.get('invoice_id', order_id)}</code>\n📦 <b>Package:</b> {product_name}\n🔢 <b>Quantity:</b> {total_qty}\n💰 <b>Total Price:</b> ${data.get('total_price')}\n\n📥 <i>Your items are inside the attached file.</i>\n➖➖➖➖➖➖➖➖➖➖")
        buy_again_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛍️ Buy Again", callback_data=f"buyprod_{product_id}", style="success")]])
        try: await bot.send_document(chat_id=user_id, document=file_id, caption=delivery_caption, parse_mode="HTML", reply_markup=buy_again_kb)
        except Exception: pass
        db.collection('orders').document(order_id).set({'order_id': order_id, 'invoice_id': data.get('invoice_id', order_id), 'user_id': user_id, 'product_id': product_id, 'product_name': product_name, 'qty': total_qty, 'total_price': data.get('total_price'), 'items_delivered': [f"File Delivered: {file_name}"], 'completed_by': 'Admin', 'timestamp': firestore.SERVER_TIMESTAMP})
        doc_ref.delete()
        if MAIN_GROUPS_ID:
            try:
                str_uid = str(user_id)
                masked_uid = f"{str_uid[:3]}***{str_uid[-2:]}" if len(str_uid) > 4 else f"{str_uid[:1]}***{str_uid[-1:]}"
                promo_text = f"🎉 <b>New Order Placed!</b>\n\n👤 User <code>{masked_uid}</code> just purchased:\n🛍️ <b>{product_name}</b>\n🔢 <b>Quantity:</b> {total_qty}\n\n⚡️ <i>Delivered securely by Admin.</i>"
                buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
                await bot.send_message(chat_id=MAIN_GROUPS_ID, text=promo_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]]))
            except Exception: pass
        await state.clear()
        try:
            await message.delete()
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
            await message.answer(f"✅ Order Delivered Successfully via File ({file_name})!")
        except Exception: pass
        return

    admin_key = message.text
    if not admin_key: return await message.answer("❌ Please send text or a file.")
    delivered_items.append(admin_key)
    
    if current_num < total_qty:
        next_num = current_num + 1
        await state.update_data(current_item_num=next_num, delivered_items=delivered_items)
        try: await message.delete()
        except: pass
        await bot.edit_message_text(f"📝 <b>Delivery Required (Item {next_num} of {total_qty})</b>\n\nPlease send the details for Item #{next_num} below:", chat_id=message.chat.id, message_id=prompt_msg_id, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_delivery", style="danger")]]))
        return
        
    delivery_text = f"✅ <b>DELIVERY SUCCESSFUL!</b>\n\n🧾 <b>Invoice:</b> <code>{data.get('invoice_id', order_id)}</code>\n📦 <b>Package:</b> {product_name}\n🔢 <b>Quantity:</b> {total_qty}\n💰 <b>Total Price:</b> ${data.get('total_price')}\n➖➖➖➖➖➖➖➖➖➖\n"
    for idx, item in enumerate(delivered_items, 1): delivery_text += f"🛍️ <b>Item {idx}:</b>\n<code>{item}</code>\n\n"
    delivery_text += "➖➖➖➖➖➖➖➖➖➖\n"
    buy_again_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛍️ Buy Again", callback_data=f"buyprod_{product_id}", style="success")]])
    try: await bot.send_message(user_id, delivery_text, parse_mode="HTML", reply_markup=buy_again_kb)
    except Exception: pass
    db.collection('orders').document(order_id).set({'order_id': order_id, 'invoice_id': data.get('invoice_id', order_id), 'user_id': user_id, 'product_id': product_id, 'product_name': product_name, 'qty': total_qty, 'total_price': data.get('total_price'), 'items_delivered': delivered_items, 'completed_by': 'Admin', 'timestamp': firestore.SERVER_TIMESTAMP})
    doc_ref.delete()
    if MAIN_GROUPS_ID:
        try:
            str_uid = str(user_id)
            masked_uid = f"{str_uid[:3]}***{str_uid[-2:]}" if len(str_uid) > 4 else f"{str_uid[:1]}***{str_uid[-1:]}"
            promo_text = f"🎉 <b>New Order Placed!</b>\n\n👤 User <code>{masked_uid}</code> just purchased:\n🛍️ <b>{product_name}</b>\n🔢 <b>Quantity:</b> {total_qty}\n\n⚡️ <i>Delivered securely by Admin.</i>"
            buy_url = f"https://t.me/{BOT_USERNAME}?start=buy_{product_id}" if product_id else f"https://t.me/{BOT_USERNAME}"
            await bot.send_message(chat_id=MAIN_GROUPS_ID, text=promo_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=buy_url)]]))
        except Exception: pass
    await state.clear()
    try:
        await message.delete()
        await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.answer("✅ Order Delivered Successfully!")
    except Exception: pass

@router.callback_query(F.data.startswith("reford_"))
async def refund_order(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    order_id = callback.data.split("_")[1]
    doc_ref = db.collection('pending_orders').document(order_id)
    doc = doc_ref.get()
    if doc.exists and doc.to_dict().get('status') == 'pending':
        data = doc.to_dict()
        user_id, total_price = data.get('user_id'), data.get('total_price')
        db.collection('users').document(str(user_id)).update({'balance': firestore.Increment(total_price), 'total_spent': firestore.Increment(-total_price)})
        doc_ref.delete()
        try: await bot.send_message(user_id, f"⚠️ <b>Order Cancelled & Refunded!</b>\n<b>${total_price}</b> returned to wallet.", parse_mode="HTML")
        except: pass
    await callback.message.delete()
    await callback.answer("Order Rejected & Refunded!", show_alert=True)

# --- Manage Products ---
@router.callback_query(F.data == "admin_products")
async def manage_products_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="admin_cat_vpn", style="primary"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="admin_cat_proxy", style="primary")],
        [InlineKeyboardButton(text="🎟️ Premium", callback_data="admin_cat_sub", style="primary"), InlineKeyboardButton(text="🤖 AI Service", callback_data="admin_cat_ai", style="primary")],
        [InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product", style="success")],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")]
    ])
    await callback.message.edit_text("📂 <b>Manage Products - Categories</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_cat_"))
async def show_category_options(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat = callback.data.split("_")[2] 
    keyboard = []
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        for sc in subcats: keyboard.append([InlineKeyboardButton(text=f"📂 {sc['name']}", callback_data=f"admin_subcat|{cat}|{sc['subcat_id']}", style="primary")])
        keyboard.append([InlineKeyboardButton(text="➕ Add Sub-Category", callback_data=f"add_subcat|{cat}", style="success")])
    else:
        if db:
            docs = db.collection('products').where('category', '==', cat).stream()
            for doc in docs:
                details = doc.to_dict()
                status_emoji = "🔴" if details.get('status') == 'paused' else ""
                keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {details.get('name')} | ${details.get('price')}", callback_data=f"editp|{doc.id}", style="primary")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back to Categories", callback_data="admin_products", style="danger")])
    await callback.message.edit_text(f"📦 <b>Manage: {cat.upper()}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_subcat|"))
async def show_category_products_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat, subcat = callback.data.split("|")[1], callback.data.split("|")[2]
    docs = db.collection('products').where('category', '==', cat).where('sub_category', '==', subcat).stream() if db else []
    keyboard = []
    for doc in docs:
        details = doc.to_dict()
        status_emoji = "🔴" if details.get('status') == 'paused' else ""
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {details.get('name', 'Unknown')} | ${details.get('price', 0.0)}", callback_data=f"editp|{doc.id}", style="primary")])
    keyboard.append([InlineKeyboardButton(text="➕ Add New Product", callback_data="add_new_product", style="success")])
    keyboard.append([InlineKeyboardButton(text="🗑️ Delete Sub-Category", callback_data=f"delsubcat|{cat}|{subcat}", style="danger")])
    keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data=f"admin_cat_{cat}", style="primary")])
    text = f"📦 <b>Manage Products</b>\n\nSelect a product to edit or delete:" if len(keyboard) > 3 else f"⚠️ <b>No products found here.</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("delsubcat|"))
async def ask_delete_subcat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat, subcat = callback.data.split("|")[1], callback.data.split("|")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"confirm_delsubcat|{cat}|{subcat}", style="danger")], [InlineKeyboardButton(text="❌ Cancel", callback_data=f"admin_subcat|{cat}|{subcat}", style="primary")]])
    await callback.message.edit_text("⚠️ <b>Are you sure you want to delete this entire sub-category?</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_delsubcat|"))
async def process_delete_subcat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cat, subcat = callback.data.split("|")[1], callback.data.split("|")[2]
    await delete_subcategory(subcat)
    await callback.answer("✅ Sub-Category deleted successfully!", show_alert=True)
    callback.data = f"admin_cat_{cat}"
    await show_category_options(callback)

# 🟢 EDIT PRODUCT (Added MOQ Button)
@router.callback_query(F.data.startswith("editp|"))
async def edit_product_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Product not found!", show_alert=True)
    
    cat, subcat = product.get('category', 'vpn'), product.get('sub_category', 'none')
    back_btn = f"admin_subcat|{cat}|{subcat}" if subcat and subcat != "none" else f"admin_cat_{cat}"
    
    stock_count = len(product.get('stock', []))
    delivery_type = product.get('delivery_type', 'manual')
    current_status = product.get('status', 'active')
    status_text = "🟢 Active" if current_status == 'active' else "🔴 Paused (Out of Stock)"
    toggle_btn_text = "🔴 Pause Product" if current_status == 'active' else "🟢 Make Active"
    is_muted = product.get('promo_muted', False)
    promo_btn_text = "🔊 Promo On" if is_muted else "🔕 Mute Promo"
    
    # 🟢 NEW: Get current Min Qty
    min_qty = product.get('min_qty', 1)
    
    text = (
        f"📦 <b>Product Details</b>\n\n"
        f"🔹 <b>Name:</b> {product.get('name')}\n"
        f"📂 <b>Category:</b> {cat.upper()}\n"
        f"💲 <b>Current Price:</b> ${product.get('price')}\n"
        f"🚚 <b>Delivery Type:</b> {delivery_type.title()}\n"
        f"🔑 <b>Keys in Stock:</b> {stock_count}\n"
        f"📉 <b>Min Order Qty:</b> {min_qty}\n" # 🟢 Shown in menu
        f"📊 <b>Status:</b> {status_text}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💲 Edit Price", callback_data=f"updatep|price|{prod_id}", style="primary"), InlineKeyboardButton(text="➕ Add Stock", callback_data=f"updatep|stock|{prod_id}", style="primary")],
        [InlineKeyboardButton(text="📝 Edit Description", callback_data=f"updatep|desc|{prod_id}", style="primary"), InlineKeyboardButton(text="🔢 Set Min Qty", callback_data=f"updatep|minqty|{prod_id}", style="primary")], # 🟢 NEW BUTTON
        [InlineKeyboardButton(text=promo_btn_text, callback_data=f"mutepromo|{prod_id}", style="primary"), InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_status|{prod_id}", style="primary")],
        [InlineKeyboardButton(text="🗑️ Delete Product", callback_data=f"delp|{prod_id}", style="danger"), InlineKeyboardButton(text="◀️ Back", callback_data=back_btn, style="primary")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("mutepromo|"))
async def toggle_promo_mute(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    product = await get_product(prod_id)
    if not product: return await callback.answer("Error loading product.")
    new_muted_status = not product.get('promo_muted', False)
    db.collection('products').document(prod_id).update({'promo_muted': new_muted_status})
    await callback.answer(f"Promo is now {'Muted' if new_muted_status else 'Unmuted'}!")
    callback.data = f"editp|{prod_id}"
    await edit_product_menu(callback)

@router.callback_query(F.data.startswith("toggle_status|"))
async def toggle_product_status(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    product = await get_product(prod_id)
    if not product: return await callback.answer("Error loading product.")
    new_status = 'paused' if product.get('status', 'active') == 'active' else 'active'
    db.collection('products').document(prod_id).update({'status': new_status})
    await callback.answer(f"Product is now {new_status.title()}!")
    
    if MAIN_CHANNEL_ID and await get_autopost_status():
        prod_name = product.get('name')
        if new_status == 'paused':
            channel_text, buy_btn = f"⚠️ <b>STOCK OUT NOTICE</b>\n\n🚫 <b>{prod_name}</b> is currently out of stock. Stay tuned for updates!", None
        else:
            channel_text, buy_btn = f"🌟 <b>NEW STOCK AVAILABLE!</b>\n\n📦 <b>{prod_name}</b> is back in stock!\n💲 <b>Price:</b> ${product.get('price')}\n\nGrab yours before it's gone!", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=f"https://t.me/{BOT_USERNAME}?start=buy_{prod_id}")]])
        try: await bot.send_message(MAIN_CHANNEL_ID, channel_text, reply_markup=buy_btn, parse_mode="HTML")
        except: pass
    callback.data = f"editp|{prod_id}"
    await edit_product_menu(callback)

@router.callback_query(F.data.startswith("updatep|"))
async def start_update_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    action, prod_id = callback.data.split("|")[1], callback.data.split("|")[2]
    product = await get_product(prod_id)
    if not product: return await callback.answer("❌ Error loading product.")
    
    await state.update_data(product_id=prod_id, old_price=product.get('price'), prod_name=product.get('name'), prod_cat=product.get('category'))
    
    if action == "price":
        await state.set_state(EditProductState.waiting_for_price)
        await callback.message.edit_text(f"💲 <b>Update Price for {product.get('name')}</b>\nCurrent Price: ${product.get('price')}\n\nEnter the new price below:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}", style="danger")]]))
    elif action == "desc":
        await state.set_state(EditProductState.waiting_for_desc)
        await callback.message.edit_text(f"📝 <b>Edit Description for {product.get('name')}</b>\nEnter the new description below.\n\n<i>Tip: You can use Telegram's bold/italic formatting, or paste raw HTML code like <code>&lt;b&gt;text&lt;/b&gt;</code>.</i>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}", style="danger")]]))
    elif action == "stock":
        await state.set_state(EditProductState.waiting_for_stock)
        cat = product.get('category', 'vpn')
        format_msg = "Format: <code>IP:Port:User:Pass</code>" if cat == "proxy" else "Format: <code>Email:Password</code>" if cat == "vpn" else "Format: <code>Link or Key</code>"
        inst = f"➕ <b>Add Stock for {product.get('name')}</b>\n\nSend a text message with multiple lines OR upload a <b>.txt</b> file.\n<i>Empty lines and extra spaces will be ignored automatically.</i>\n\n🔹 {format_msg}"
        await callback.message.edit_text(inst, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}", style="danger")]]))
    elif action == "minqty": # 🟢 NEW: Handle Min Qty state
        await state.set_state(EditProductState.waiting_for_minqty)
        await callback.message.edit_text(f"🔢 <b>Set Minimum Order Qty for {product.get('name')}</b>\nCurrent Min Qty: {product.get('min_qty', 1)}\n\nEnter the new minimum quantity (e.g., 5 or 10):", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}", style="danger")]]))

# 🟢 NEW: Process Min Qty
@router.message(EditProductState.waiting_for_minqty)
async def process_minqty_update(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit(): return await message.answer("❌ Please enter a valid number.")
    min_qty = int(message.text)
    if min_qty < 1: min_qty = 1
    
    data = await state.get_data()
    prod_id = data['product_id']
    
    if db: db.collection('products').document(prod_id).update({'min_qty': min_qty, 'updated_at': firestore.SERVER_TIMESTAMP})
    await state.clear()
    await message.answer(f"✅ Minimum Order Qty updated to: <b>{min_qty}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Product", callback_data=f"editp|{prod_id}", style="primary")]]))

@router.message(EditProductState.waiting_for_desc)
async def process_desc_update(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    raw_text = message.text or ""
    html_tags = ["<b>", "<i>", "<u>", "<s>", "<code>", "<pre>", "<blockquote>", "<a href"]
    new_desc = raw_text if any(tag in raw_text.lower() for tag in html_tags) else message.html_text 
    data = await state.get_data()
    prod_id = data['product_id']
    if db: db.collection('products').document(prod_id).update({'description': new_desc, 'updated_at': firestore.SERVER_TIMESTAMP})
    await state.clear()
    await message.answer(f"✅ Description updated successfully!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Product", callback_data=f"editp|{prod_id}", style="primary")]]))

@router.message(EditProductState.waiting_for_price)
async def process_price_update(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    try: new_price = float(message.text)
    except ValueError: return await message.answer("❌ Invalid price format. Try again.")
    data = await state.get_data()
    prod_id, old_price, prod_name = data['product_id'], data['old_price'], data['prod_name']
    if db: db.collection('products').document(prod_id).update({'price': new_price, 'updated_at': firestore.SERVER_TIMESTAMP})
    await state.clear()
    await message.answer(f"✅ Price updated successfully to ${new_price}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Product", callback_data=f"editp|{prod_id}", style="primary")]]))
    if MAIN_CHANNEL_ID and old_price != new_price and await get_autopost_status():
        trend = "📉 <b>PRICE DROP!</b>" if new_price < old_price else "📈 <b>PRICE UPDATE</b>"
        channel_text = f"{trend}\n\n📦 <b>{prod_name}</b>\n❌ Old Price: ${old_price}\n✅ <b>New Price: ${new_price}</b>\n\nGet it now from our bot!"
        try: await bot.send_message(MAIN_CHANNEL_ID, channel_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=f"https://t.me/{BOT_USERNAME}?start=buy_{prod_id}")]]), parse_mode="HTML")
        except: pass

@router.message(EditProductState.waiting_for_stock)
async def process_stock_update(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    raw_text = ""
    if message.document:
        if not message.document.file_name.endswith('.txt'): return await message.answer("❌ Please upload a valid .txt file or send text.")
        file_info = await bot.get_file(message.document.file_id)
        raw_text = (await bot.download_file(file_info.file_path)).read().decode('utf-8')
    elif message.text: raw_text = message.text
    else: return await message.answer("❌ Invalid input. Send text or a .txt file.")
        
    valid_keys = [k.strip() for k in raw_text.splitlines() if k.strip()]
    if not valid_keys: return await message.answer("❌ No valid data found. Try again.")
    
    data = await state.get_data()
    prod_id = data['product_id']
    if db:
        doc = db.collection('products').document(prod_id).get()
        if doc.exists:
            current_stock = doc.to_dict().get('stock', [])
            current_stock.extend(valid_keys)
            db.collection('products').document(prod_id).update({'stock': current_stock, 'status': 'active', 'delivery_type': 'auto', 'updated_at': firestore.SERVER_TIMESTAMP})
    await state.clear()
    await message.answer(f"✅ <b>{len(valid_keys)} Keys Added to Stock!</b>\nDelivery Type is now set to <b>Auto</b>.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Product", callback_data=f"editp|{prod_id}", style="primary")]]))

@router.callback_query(F.data.startswith("delp|"))
async def ask_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"confirm_delp|{prod_id}", style="danger")], [InlineKeyboardButton(text="❌ Cancel", callback_data=f"editp|{prod_id}", style="primary")]])
    await callback.message.edit_text("⚠️ <b>Are you sure you want to permanently delete this product?</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_delp|"))
async def process_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    prod_id = callback.data.split("|")[1]
    product = await get_product(prod_id)
    cat, subcat = product.get('category', 'vpn') if product else 'vpn', product.get('sub_category', 'none') if product else 'none'
    await delete_product(prod_id)
    await callback.answer("✅ Product deleted!", show_alert=True)
    if subcat and subcat != "none":
        callback.data = f"admin_subcat|{cat}|{subcat}"
        await show_category_products_sub(callback)
    else:
        callback.data = f"admin_cat_{cat}"
        await show_category_options(callback)

@router.callback_query(F.data.startswith("add_subcat|"))
async def add_subcat_start(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split("|")[1]
    await state.update_data(category=cat)
    await state.set_state(AddSubCatState.name)
    await callback.message.edit_text(f"📝 Enter name for new <b>{cat.upper()}</b> sub-category (e.g., 7 Days Validity):", parse_mode="HTML")

@router.message(AddSubCatState.name)
async def save_subcat(message: Message, state: FSMContext):
    data = await state.get_data()
    cat = data['category']
    await add_subcategory(cat, message.text)
    await state.clear()
    await message.answer(f"✅ Sub-category added to {cat.upper()}!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data=f"admin_cat_{cat}", style="primary")]]))

@router.callback_query(F.data == "add_new_product")
async def add_product_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 VPN", callback_data="setcat_vpn", style="primary"), InlineKeyboardButton(text="🛡️ Proxy", callback_data="setcat_proxy", style="primary")],
        [InlineKeyboardButton(text="🎟️ Premium", callback_data="setcat_sub", style="primary"), InlineKeyboardButton(text="🤖 AI Service", callback_data="setcat_ai", style="primary")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_products", style="danger")]
    ])
    await callback.message.edit_text("📂 <b>Select a Category for the new product:</b>", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("setcat_"))
async def add_product_subcat(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split("_")[1]
    await state.update_data(prod_category=cat)
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        if not subcats: return await callback.answer("⚠️ Create a sub-category first!", show_alert=True)
        keyboard = [[InlineKeyboardButton(text=sc['name'], callback_data=f"setsubcat|{sc['subcat_id']}", style="primary")] for sc in subcats]
        await callback.message.edit_text("📂 Select Sub-Category:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await state.update_data(prod_subcat="none")
        await state.set_state(AddProductState.name)
        await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("setsubcat|"))
async def add_product_name_sub(callback: CallbackQuery, state: FSMContext):
    await state.update_data(prod_subcat=callback.data.split("|")[1])
    await state.set_state(AddProductState.name)
    await callback.message.edit_text("📝 <b>Enter Product Name:</b>", parse_mode="HTML")

@router.message(AddProductState.name)
async def add_product_price(message: Message, state: FSMContext):
    await state.update_data(prod_name=message.text)
    await state.set_state(AddProductState.price)
    await message.answer("💲 <b>Enter Product Price ($):</b>\n(e.g., 2.50)", parse_mode="HTML")

@router.message(AddProductState.price)
async def add_product_description(message: Message, state: FSMContext):
    try: price = float(message.text)
    except ValueError: return await message.answer("❌ Invalid price format.")
    await state.update_data(prod_price=price)
    await state.set_state(AddProductState.description)
    await message.answer("📝 <b>Enter Product Description:</b>\n(You can use Telegram's bold/italic formatting, paste raw HTML, or click Skip to use the default)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip (Use Default)", callback_data="skip_desc")]]), parse_mode="HTML")

@router.callback_query(F.data == "skip_desc")
async def save_new_product_skip_desc(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await save_product_to_db(callback.message, state, bot, desc=None)
    await callback.answer()

@router.message(AddProductState.description)
async def save_new_product_with_desc(message: Message, state: FSMContext, bot: Bot):
    html_tags = ["<b>", "<i>", "<u>", "<s>", "<code>", "<pre>", "<blockquote>", "<a href"]
    desc = message.text if any(tag in (message.text or "").lower() for tag in html_tags) else message.html_text
    await save_product_to_db(message, state, bot, desc=desc)

async def save_product_to_db(message: Message, state: FSMContext, bot: Bot, desc: str = None):
    data = await state.get_data()
    price = data['prod_price']
    new_prod_id = f"p{int(time.time() * 1000) % 100000}" 
    
    prod_data = {
        'product_id': new_prod_id, 'category': data['prod_category'], 'sub_category': data['prod_subcat'],
        'name': data['prod_name'], 'price': price, 'delivery_type': 'manual', 'stock': [],
        'status': 'active', 'promo_muted': False, 'min_qty': 1, # 🟢 Default min qty 1
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    if desc: prod_data['description'] = desc
    if db: db.collection('products').document(new_prod_id).set(prod_data)
        
    if MAIN_CHANNEL_ID and await get_autopost_status():
        try: await bot.send_message(MAIN_CHANNEL_ID, f"🌟 <b>NEW PRODUCT ADDED!</b> 🌟\n\n📦 <b>{data['prod_name']}</b>\n💲 <b>Price:</b> ${price}\n\nAvailable now in our bot!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Buy Now", url=f"https://t.me/{BOT_USERNAME}?start=buy_{new_prod_id}")]]), parse_mode="HTML")
        except: pass
        
    await state.clear()
    await message.answer(f"✅ <b>Product Added Successfully!</b>\n📦 {data['prod_name']} - ${price}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="primary")]]), parse_mode="HTML")

# --- Users Management ---
@router.callback_query(F.data == "admin_users")
async def manage_users_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(callback.from_user.id): return
    users_count = len(list(db.collection('users').stream())) if db else 0
    await callback.message.edit_text(f"👥 <b>User Management</b>\n\n📊 <b>Total Registered Users:</b> {users_count}\n\nClick below to search for a user.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Search & Edit User", callback_data="search_user", style="primary")], [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="danger")]]), parse_mode="HTML")

@router.callback_query(F.data == "search_user")
async def search_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(UserManageState.waiting_for_user_id)
    await callback.message.edit_text("🔍 <b>Enter User ID:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users", style="danger")]]), parse_mode="HTML")

@router.message(UserManageState.waiting_for_user_id)
async def search_user_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.text.isdigit(): return await message.answer("❌ Invalid ID.")
    target_uid = message.text
    doc = db.collection('users').document(target_uid).get() if db else None
    if not doc or not doc.exists: return await message.answer("❌ User not found.")
        
    user_info = doc.to_dict()
    await state.update_data(target_user=target_uid)
    text = (f"👤 <b>User Details</b>\n\n🆔 <b>ID:</b> <code>{target_uid}</code>\n📛 <b>Name:</b> {user_info.get('first_name', 'Unknown')}\n"
            f"🔗 <b>Username:</b> @{user_info.get('username')} \n💰 <b>Balance:</b> ${user_info.get('balance', 0.0):.2f}\n💸 <b>Spent:</b> ${user_info.get('total_spent', 0.0):.2f}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add Balance", callback_data=f"addbal_{target_uid}", style="success"), InlineKeyboardButton(text="➖ Deduct Balance", callback_data=f"dedbal_{target_uid}", style="danger")], [InlineKeyboardButton(text="🧹 Clear Test Data", callback_data=f"cleardata_{target_uid}", style="danger")], [InlineKeyboardButton(text="◀️ Back", callback_data="search_user", style="primary")]])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("cleardata_"))
async def clear_test_data(callback: CallbackQuery):
    if not is_admin(callback.from_user.id) or not db: return
    target_uid = callback.data.split("_")[1]
    db.collection('users').document(str(target_uid)).update({'balance': 0.0, 'total_spent': 0.0})
    for col in ['orders', 'pending_orders', 'deposit_history']:
        for doc in db.collection(col).where('user_id', '==', int(target_uid)).stream(): doc.reference.delete()
    await callback.answer(f"✅ All Test Orders & Deposits cleared for User {target_uid}!", show_alert=True)
    message = callback.message; message.text = target_uid; message.from_user = callback.from_user
    await search_user_result(message, FSMContext(storage=None, key=None)) 

@router.callback_query(F.data.startswith("addbal_") | F.data.startswith("dedbal_"))
async def ask_balance_amount(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    action, target_uid = callback.data.split("_")
    await state.update_data(action_type=action, target_user=target_uid)
    await state.set_state(UserManageState.waiting_for_amount)
    await callback.message.edit_text(f"💲 <b>Enter Amount to {'ADD to' if action == 'addbal' else 'DEDUCT from'} User <code>{target_uid}</code>:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_users", style="danger")]]), parse_mode="HTML")

@router.message(UserManageState.waiting_for_amount)
async def process_balance_change(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    try: amount = float(message.text)
    except ValueError: return await message.answer("❌ Invalid amount.")
    data = await state.get_data()
    target_uid, action = data['target_user'], data['action_type']
    user_ref = db.collection('users').document(str(target_uid)) if db else None
    if user_ref:
        if action == "addbal":
            user_ref.update({'balance': firestore.Increment(amount)})
            try: await bot.send_message(target_uid, f"🎁 <b>Balance Added!</b>\nAdmin added <b>${amount}</b> to your wallet.", parse_mode="HTML")
            except: pass
        else:
            user_ref.update({'balance': firestore.Increment(-amount)})
            try: await bot.send_message(target_uid, f"⚠️ <b>Balance Deducted</b>\nAdmin deducted <b>${amount}</b> from your wallet.", parse_mode="HTML")
            except: pass
    await state.clear()
    new_balance = user_ref.get().to_dict().get('balance', 0.0) if user_ref and user_ref.get().exists else 0.0
    await message.answer(f"✅ <b>Success!</b>\n\n👤 <b>User:</b> <code>{target_uid}</code>\n💰 <b>New Balance:</b> ${new_balance:.2f}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="back_to_admin", style="primary")]]), parse_mode="HTML")

# --- Broadcast ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.edit_text("📢 <b>Broadcast Message</b>\n\nSend the message, photo, or video you want to broadcast.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin", style="danger")]]), parse_mode="HTML")

@router.message(BroadcastState.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    await show_broadcast_button_menu(message, state)

@router.callback_query(BroadcastState.waiting_for_button, F.data == "bc_back_to_btn_menu")
@router.callback_query(BroadcastState.waiting_for_custom_btn, F.data == "bc_back_to_btn_menu")
async def back_to_broadcast_button_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await show_broadcast_button_menu(callback.message, state, is_callback=True)

async def show_broadcast_button_menu(message_or_callback, state: FSMContext, is_callback=False):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Send Without Button", callback_data="bc_btn|none", style="success")],
        [InlineKeyboardButton(text="🤖 Open Bot (Start)", callback_data="bc_btn|start", style="primary"), InlineKeyboardButton(text="🛒 Open Shop", callback_data="bc_btn|shop", style="primary")],
        [InlineKeyboardButton(text="➕ Custom Link Button", callback_data="bc_custom_btn", style="primary")],
        [InlineKeyboardButton(text="🛍️ Attach a Product", callback_data="bc_list_prods", style="primary")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin", style="danger")]
    ])
    await state.set_state(BroadcastState.waiting_for_button)
    text = "🎯 <b>What kind of button do you want to attach?</b>"
    if is_callback: await message_or_callback.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else: await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(BroadcastState.waiting_for_button, F.data == "bc_list_prods")
async def show_product_list_for_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    keyboard = [[InlineKeyboardButton(text=f"🔗 Attach: {doc.to_dict()['name']}", callback_data=f"bc_btn|prod_{doc.id}", style="primary")] for doc in db.collection('products').stream()] if db else []
    keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="bc_back_to_btn_menu", style="danger")])
    await callback.message.edit_text("🛒 <b>Select a product to attach:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(BroadcastState.waiting_for_button, F.data == "bc_custom_btn")
async def ask_custom_button(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(BroadcastState.waiting_for_custom_btn)
    await callback.message.edit_text("📝 <b>Send button details:</b>\nFormat: <code>Button Text - https://link.com</code>\n\nExample:\n<code>Join Channel - https://t.me/mychannel</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="bc_back_to_btn_menu", style="danger")]]))

@router.message(BroadcastState.waiting_for_custom_btn)
async def process_custom_button(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if " - " not in message.text: return await message.answer("❌ Invalid format! Use: <code>Text - URL</code>", parse_mode="HTML")
    await state.update_data(product_btn_id=f"custom|{message.text}")
    await ask_broadcast_destination_msg(message, state)

@router.callback_query(BroadcastState.waiting_for_button, F.data.startswith("bc_btn|"))
async def ask_broadcast_destination_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.update_data(product_btn_id=callback.data.split("|")[1])
    await ask_broadcast_destination_msg(callback.message, state, is_callback=True)

async def ask_broadcast_destination_msg(message_or_callback, state: FSMContext, is_callback=False):
    await state.set_state(BroadcastState.waiting_for_destination)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👥 Users Only", callback_data="bc_dest|users", style="primary")], [InlineKeyboardButton(text="📢 Channel Only", callback_data="bc_dest|channel", style="primary")], [InlineKeyboardButton(text="🌍 Send to Both", callback_data="bc_dest|both", style="success")], [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_admin", style="danger")]])
    text = "🎯 <b>Where do you want to send this broadcast?</b>"
    if is_callback: await message_or_callback.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else: await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(BroadcastState.waiting_for_destination, F.data.startswith("bc_dest|"))
async def execute_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id): return
    destination = callback.data.split("|")[1]
    user_data = await state.get_data()
    msg_id, from_chat_id, btn_data = user_data['msg_id'], user_data['from_chat_id'], user_data.get('product_btn_id', 'none')
    
    reply_markup = None
    if btn_data != "none":
        if btn_data == "start": reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🤖 Open Bot", url=f"https://t.me/{BOT_USERNAME}")]])
        elif btn_data == "shop": reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Open Shop", url=f"https://t.me/{BOT_USERNAME}") ]])
        elif btn_data.startswith("custom|"): 
            text, url = btn_data.split("custom|")[1].split(" - ", 1)
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text.strip(), url=url.strip())]])
        elif btn_data.startswith("prod_") and db:
            product = db.collection('products').document(btn_data.split("prod_")[1]).get().to_dict()
            if product: reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🛒 Buy {product['name']} - ${product['price']}", url=f"https://t.me/{BOT_USERNAME}?start=buy_{btn_data.split('prod_')[1]}")]])
            
    await state.clear()
    await callback.message.edit_text("⏳ <b>Broadcasting...</b>\nPlease wait.")
    
    success_count, channel_sent = 0, False
    if destination in ['channel', 'both'] and MAIN_CHANNEL_ID:
        try: await bot.copy_message(chat_id=MAIN_CHANNEL_ID, from_chat_id=from_chat_id, message_id=msg_id, reply_markup=reply_markup); channel_sent = True
        except: pass
    if destination in ['users', 'both']:
        users = [doc.id for doc in db.collection('users').stream()] if db else [str(callback.from_user.id)]
        for uid in users:
            try: await bot.copy_message(chat_id=int(uid), from_chat_id=from_chat_id, message_id=msg_id, reply_markup=reply_markup); success_count += 1
            except: pass 
            
    result_text = "✅ <b>Broadcast Complete!</b>\n\n"
    if destination in ['users', 'both']: result_text += f"👥 Sent to <b>{success_count}</b> users.\n"
    if destination in ['channel', 'both']: result_text += f"📢 Posted to channel: {'✅ Yes' if channel_sent else '❌ Failed'}"
    await callback.message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Back to Dashboard", callback_data="back_to_admin", style="primary")]]), parse_mode="HTML")
