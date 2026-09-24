# ==========================================
# File: handlers/proxy_checker.py
# Purpose: Advanced Universal Proxy Checker (Bulk SOCKS5 Checker)
# ==========================================
import asyncio
import io
import pandas as pd
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyError
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class ProxyCheckState(StatesGroup):
    waiting_for_proxies = State()

# 🟢 সিঙ্গেল প্রক্সি চেক করার ফাংশন
async def check_single_proxy(proxy_str: str) -> dict:
    # Format: host:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) != 4:
        return {"proxy": proxy_str, "status": "Invalid Format", "is_live": False}
    
    host, port, user, password = parts
    proxy_url = f"socks5://{user}:{password}@{host}:{port}"
    
    try:
        connector = ProxyConnector.from_url(proxy_url)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 10-second timeout
            async with session.get("https://api.ipify.org?format=json", timeout=10) as response:
                if response.status == 200:
                    return {"proxy": proxy_str, "status": "Live", "is_live": True}
                else:
                    return {"proxy": proxy_str, "status": f"Dead (HTTP {response.status})", "is_live": False}
    except asyncio.TimeoutError:
        return {"proxy": proxy_str, "status": "Timeout", "is_live": False}
    except ProxyError:
        return {"proxy": proxy_str, "status": "Proxy Error", "is_live": False}
    except Exception:
        return {"proxy": proxy_str, "status": "Connection Error", "is_live": False}

# 🟢 একসাথে অনেকগুলো প্রক্সি চেক করার কনকারেন্ট ফাংশন
async def check_proxies_concurrently(proxies: list) -> list:
    tasks = [check_single_proxy(p) for p in proxies]
    # একবারে ৫০টা করে প্রক্সি চেক করবে সার্ভার প্রেশার এড়াতে
    semaphore = asyncio.Semaphore(50)
    
    async def sem_task(task):
        async with semaphore:
            return await task
            
    return await asyncio.gather(*(sem_task(t) for t in tasks))

@router.callback_query(F.data == "check_proxy")
async def start_proxy_check(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProxyCheckState.waiting_for_proxies)
    
    text = (
        "🔍 <b>Advanced SOCKS5 Proxy Checker</b>\n\n"
        "Please send the proxies you want to check.\n"
        "<b>Format:</b> <code>host:port:user:pass</code>\n\n"
        "<i>You can paste them as a text message, or upload a .txt or .xlsx file.</i>"
    )
    # 🟢 FIXED: Cancel এর বদলে ◀️ Back বাটন দেওয়া হলো
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back", callback_data="menu_buy")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(ProxyCheckState.waiting_for_proxies)
async def handle_proxy_input(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    proxies = []
    
    status_msg = await message.answer("⏳ <b>Processing your input...</b>", parse_mode="HTML")
    
    # ফাইল থেকে প্রক্সি রিড করা
    if message.document:
        file_name = message.document.file_name.lower()
        if not (file_name.endswith('.txt') or file_name.endswith('.xlsx')):
            return await status_msg.edit_text("❌ Please upload a valid .txt or .xlsx file.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Try Again", callback_data="check_proxy")]]))
            
        file_info = await bot.get_file(message.document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        if file_name.endswith('.txt'):
            raw_text = downloaded_file.read().decode('utf-8')
            proxies = [p.strip() for p in raw_text.splitlines() if p.strip()]
        elif file_name.endswith('.xlsx'):
            try:
                df = pd.read_excel(io.BytesIO(downloaded_file.read()))
                col_name = 'Proxy' if 'Proxy' in df.columns else df.columns[0]
                raw_proxies = df[col_name].dropna().astype(str).tolist()
                proxies = [p.replace("socks5://", "").strip() for p in raw_proxies if p.strip()]
            except Exception as e:
                return await status_msg.edit_text(f"❌ Error reading Excel file: {e}")
                
    # টেক্সট মেসেজ থেকে প্রক্সি রিড করা
    elif message.text:
        proxies = [p.strip() for p in message.text.splitlines() if p.strip()]
        
    else:
        return await status_msg.edit_text("❌ Invalid input. Please send text or a file.")

    if not proxies:
        return await status_msg.edit_text("⚠️ No proxies found. Please check your format.")

    # ডুপ্লিকেট রিমুভ করা
    proxies = list(dict.fromkeys(proxies))
    total_proxies = len(proxies)
    
    await status_msg.edit_text(f"🚀 <b>Checking {total_proxies} proxies...</b>\n<i>This might take a few seconds depending on the quantity.</i>", parse_mode="HTML")
    
    # প্রক্সি চেকিং স্টার্ট
    results = await check_proxies_concurrently(proxies)
    
    # লাইভ এবং ডেড প্রক্সি আলাদা করা
    live_proxies = [r['proxy'] for r in results if r['is_live']]
    dead_proxies = [f"{r['proxy']} - {r['status']}" for r in results if not r['is_live']]
    
    summary = (
        f"📊 <b>Proxy Check Complete!</b>\n\n"
        f"🔹 <b>Total Checked:</b> {total_proxies}\n"
        f"✅ <b>Live:</b> {len(live_proxies)}\n"
        f"❌ <b>Dead:</b> {len(dead_proxies)}\n"
    )
    
    # 🟢 FIXED: বাটন কাজ করানোর জন্য ফাইল এবং টেক্সট মেসেজ আলাদা করা হলো
    await status_msg.delete()
    
    # লাইভ প্রক্সির ফাইল পাঠানো
    if live_proxies:
        live_data = "\n".join(live_proxies)
        live_file = BufferedInputFile(live_data.encode('utf-8'), filename="Live_Proxies.txt")
        await message.answer_document(document=live_file, caption="✅ <b>Live Proxies</b>", parse_mode="HTML")

    # ডেড প্রক্সির ফাইল পাঠানো
    if dead_proxies:
        dead_data = "\n".join(dead_proxies)
        dead_file = BufferedInputFile(dead_data.encode('utf-8'), filename="Dead_Proxies.txt")
        await message.answer_document(document=dead_file, caption="❌ <b>Dead Proxies</b>", parse_mode="HTML")

    if not live_proxies and not dead_proxies:
        summary += "\n⚠️ <i>No valid proxies were processed.</i>"
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Check More Proxies", callback_data="check_proxy")],
        [InlineKeyboardButton(text="◀️ Back to Shop", callback_data="menu_buy")]
    ])
    
    # শেষে বাটনসহ সামারি মেসেজ পাঠানো
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")
