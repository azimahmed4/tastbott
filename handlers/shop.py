# handlers/shop.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import get_products_by_category, get_product, get_subcategories

router = Router()

ITEMS_PER_PAGE = 10 # প্রতি পেজে সর্বোচ্চ ১০টি প্রোডাক্ট (৫ লাইন x ২ কলাম)

@router.callback_query(F.data == "menu_buy")
async def show_categories(callback: CallbackQuery):
    text = "🛒 <b>Shop Categories</b>\n\nPlease select a category:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 VPN", callback_data="showcat_vpn"),
            InlineKeyboardButton(text="🛡️ Proxy", callback_data="showcat_proxy")
        ],
        [
            InlineKeyboardButton(text="🎟️ Subscription", callback_data="showcat_sub"),
            InlineKeyboardButton(text="🤖 AI Service", callback_data="showcat_ai")
        ],
        [InlineKeyboardButton(text="◀️ Go Back", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("showcat_"))
async def show_subcategories_or_products(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    
    if cat in ['vpn', 'proxy']:
        subcats = await get_subcategories(cat)
        keyboard = []
        # ২ কলামে সাব-ক্যাটাগরি সাজানো
        for i in range(0, len(subcats), 2):
            row = [InlineKeyboardButton(text=f"📅 {subcats[i]['name']}", callback_data=f"shop_p_{cat}_{subcats[i]['subcat_id']}_0")]
            if i + 1 < len(subcats):
                row.append(InlineKeyboardButton(text=f"📅 {subcats[i+1]['name']}", callback_data=f"shop_p_{cat}_{subcats[i+1]['subcat_id']}_0"))
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton(text="◀️ Back", callback_data="menu_buy")])
        await callback.message.edit_text(f"📂 <b>Select Validity/Type:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        # প্রিমিয়াম এবং এআই এর জন্য সরাসরি প্রোডাক্ট লিস্ট (page 0)
        await display_products(callback, cat, "none", 0)

# পেজিনেশন হ্যান্ডলার
@router.callback_query(F.data.startswith("shop_p_"))
async def handle_pagination(callback: CallbackQuery):
    parts = callback.data.split("_")
    cat = parts[2]
    subcat = parts[3]
    page = int(parts[4])
    await display_products(callback, cat, subcat, page)

async def display_products(callback: CallbackQuery, cat: str, subcat: str, page: int):
    products_dict = await get_products_by_category(cat, subcat)
    products_list = list(products_dict.items())
    
    total_products = len(products_list)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_products = products_list[start_idx:end_idx]
    
    keyboard = []
    # 🚀 ২ কলাম লেআউট লজিক (image_6f198c.png এর মতো)
    for i in range(0, len(current_products), 2):
        pid1, details1 = current_products[i]
        row = [InlineKeyboardButton(text=f" {details1['name']}", callback_data=f"buy_{pid1}")]
        
        if i + 1 < len(current_products):
            pid2, details2 = current_products[i+1]
            row.append(InlineKeyboardButton(text=f" {details2['name']}", callback_data=f"buy_{pid2}"))
        keyboard.append(row)
        
    # 🚀 পেজিনেশন বাটন (Next/Back)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=f"shop_p_{cat}_{subcat}_{page-1}"))
    if end_idx < total_products:
        nav_row.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"shop_p_{cat}_{subcat}_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
        
    back_target = f"showcat_{cat}" if cat in ['vpn', 'proxy'] else "menu_buy"
    keyboard.append([InlineKeyboardButton(text="🏠 Back to Categories", callback_data=back_target)])
    
    text = "📦 <b>Select a Package:</b>" if current_products else "⚠️ <b>No products found here.</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# (কোয়ান্টিটি স্লাইডারের buy_ এবং setqty_ ফাংশনগুলো আগের মতোই থাকবে, স্পেস কমানোর জন্য স্কিপ করা হলো)
