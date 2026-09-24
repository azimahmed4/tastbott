
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
        return {"proxy": proxy_str, "status": "Dead (Timeout)", "is_live": False}
    except ProxyError:
        return {"proxy": proxy_str, "status": "Dead (Proxy Error)", "is_live": False}
    except Exception:
        return {"proxy": proxy_str, "status": "Dead (Connection Error)", "is_live": False}

async def check_proxies_concurrently(proxies: list) -> list:
    tasks = [check_single_proxy(p) for p in proxies]
    # একবারে 50 টা করে প্রক্সি চেক করবে যাতে সার্ভারে প্রেশার না পড়ে
    semaphore = asyncio.Semaphore(50)
    
    async def sem_task(task):
        async with semaphore:
            return await task
            
    return await asyncio.gather(*(sem_task(t) for t in tasks))

@router.callback_query(F.data == "check_proxy")
async def start_proxy_check(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProxyCheckState.waiting_for_proxies)
    
    text = (
        "🔍 <b>SOCKS5 Proxy Checker</b>\n\n"
        "Please send the proxies you want to check.\n"
        "<b>Format:</b> <code>host:port:user:pass</code>\n\n"
        "<i>You can paste them as a text message, or upload a .txt or .xlsx file.</i>"
    )
    # প্রক্সি ক্যাটাগরিতে ব্যাক করার বাটন
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="showcat_proxy")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(ProxyCheckState.waiting_for_proxies)
async def handle_proxy_input(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    proxies = []
    
    status_msg = await message.answer("⏳ Processing your input...")
    
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
                # 'Proxy' নামের কলাম খুঁজবে, না পেলে প্রথম কলামটাই নিয়ে নেবে
                col_name = 'Proxy' if 'Proxy' in df.columns else df.columns[0]
                raw_proxies = df[col_name].dropna().astype(str).tolist()
                proxies = [p.replace("socks5://", "").strip() for p in raw_proxies if p.strip()]
            except Exception as e:
                return await status_msg.edit_text(f"❌ Error reading Excel file: {e}")
                
    elif message.text:
        proxies = [p.strip() for p in message.text.splitlines() if p.strip()]
        
    else:
        return await status_msg.edit_text("❌ Invalid input. Please send text or a file.")

    if not proxies:
        return await status_msg.edit_text("⚠️ No proxies found. Please check your format.")

    # ডুপ্লিকেট প্রক্সি রিমুভ করা
    proxies = list(dict.fromkeys(proxies))
    total_proxies = len(proxies)
    
    await status_msg.edit_text(f"🚀 <b>Checking {total_proxies} proxies...</b>\nThis might take a few seconds depending on the quantity.", parse_mode="HTML")
    
    results = await check_proxies_concurrently(proxies)
    
    live_proxies = [r['proxy'] for r in results if r['is_live']]
    dead_count = total_proxies - len(live_proxies)
    
    summary = (
        f"📊 <b>Proxy Check Results</b>\n\n"
        f"🔹 <b>Total Checked:</b> {total_proxies}\n"
        f"✅ <b>Live:</b> {len(live_proxies)}\n"
        f"❌ <b>Dead:</b> {dead_count}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Back to Proxy Shop", callback_data="showcat_proxy")]])
    
    if not live_proxies:
        summary += "\n⚠️ <i>No live proxies found.</i>"
        await status_msg.edit_text(summary, reply_markup=keyboard, parse_mode="HTML")
    else:
        summary += "\n📥 <i>Your live proxies are in the file below.</i>"
        await status_msg.delete()
        
        # শুধুমাত্র লাইভ প্রক্সি দিয়ে নতুন txt ফাইল তৈরি
        output_data = "\n".join(live_proxies)
        output_file = BufferedInputFile(output_data.encode('utf-8'), filename="Live_Proxies.txt")
        
        await message.answer_document(
            document=output_file,
            caption=summary,
            parse_mode="HTML",
            reply_markup=keyboard
        )
