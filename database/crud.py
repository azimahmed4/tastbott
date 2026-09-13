# ==========================================
# File: database/crud.py
# ==========================================
import os
import json
import random
import string
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS")

db = None
if firebase_creds_json:
    try:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Connected Successfully!")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")
else:
    print("⚠️ FIREBASE_CREDENTIALS not found!")

# ==========================================
# 🟢 NEW: Bot Maintenance Mode Settings
# ==========================================
async def set_bot_status(is_maintenance: bool):
    """বটের মেইনটেনেন্স স্ট্যাটাস অন/অফ করবে"""
    if not db: return False
    db.collection('settings').document('bot_status').set({
        'maintenance': is_maintenance,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return True

async def get_bot_status():
    """বট কি এখন মেইনটেনেন্সে আছে নাকি লাইভ, সেটা চেক করবে"""
    if not db: return False
    doc = db.collection('settings').document('bot_status').get()
    if doc.exists:
        return doc.to_dict().get('maintenance', False)
    return False

# ==========================================
# 🟢 NEW: Dynamic Payment Settings
# ==========================================
async def initialize_payment_methods():
    """ডিফল্ট পেমেন্ট মেথডগুলো ডাটাবেসে সেট করবে (যদি না থাকে)"""
    if not db: return False
    
    defaults = {
        "binance": {"name": "Binance Pay", "type": "crypto", "pay_id": "1126025983", "is_active": True},
        "bybit": {"name": "Bybit Internal", "type": "crypto", "pay_id": "127145762", "is_active": True},
        "bybitaddress": {"name": "USDT (BEP20)", "type": "crypto", "address": "0x822ee632c8223cb5b0457e6a8a36221bbe52a87c", "is_active": True},
        "bkash": {"name": "bKash", "type": "local", "number": "01308618044", "is_active": True},
        "nagad": {"name": "Nagad", "type": "local", "number": "01308618044", "is_active": True},
        "rocket": {"name": "Rocket", "type": "local", "number": "01308618044", "is_active": True}
    }
    
    doc = db.collection('settings').document('payment_methods').get()
    if not doc.exists:
        db.collection('settings').document('payment_methods').set(defaults)
        return defaults
    return doc.to_dict()

async def get_all_payment_methods():
    """ডাটাবেস থেকে সব পেমেন্ট মেথডের লাইভ ডাটা আনবে"""
    if not db: return {}
    doc = db.collection('settings').document('payment_methods').get()
    if doc.exists:
        return doc.to_dict()
    # যদি ডাটাবেসে কিছুই না থাকে, তবে ডিফল্টগুলো ক্রিয়েট করে নেবে
    return await initialize_payment_methods()

async def update_payment_method(method_key: str, data: dict):
    """অ্যাডমিন প্যানেল থেকে কোনো মেথড আপডেট বা ON/OFF করার জন্য"""
    if not db: return False
    # পুরো ডকুমেন্ট আপডেট না করে শুধু নির্দিষ্ট key-এর ডাটা আপডেট করা
    db.collection('settings').document('payment_methods').update({
        method_key: data
    })
    return True

# ==========================================
# Database Functions - Users
# ==========================================
async def add_user(user_id: int, username: str, first_name: str, referred_by: int = None):
    if not db: return False
    user_ref = db.collection('users').document(str(user_id))
    doc = user_ref.get()
    if not doc.exists:
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'balance': 0.0,
            'total_referrals': 0,
            'referred_by': str(referred_by) if referred_by else None,
            'joined_at': firestore.SERVER_TIMESTAMP,
            'total_spent': 0.0
        }
        user_ref.set(user_data)
        if referred_by and str(referred_by) != str(user_id):
            referrer_ref = db.collection('users').document(str(referred_by))
            if referrer_ref.get().exists:
                referrer_ref.update({'total_referrals': firestore.Increment(1)})
        return True
    return False

async def get_user(user_id: int):
    if not db: return None
    doc = db.collection('users').document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None

# ==========================================
# Database Functions - Sub-Categories
# ==========================================
async def add_subcategory(category: str, name: str):
    if not db: return False
    subcat_id = f"{category}_{name.lower().replace(' ', '_')}"
    db.collection('subcategories').document(subcat_id).set({
        'subcat_id': subcat_id,
        'category': category,
        'name': name
    })
    return True

async def get_subcategories(category: str):
    if not db: return []
    docs = db.collection('subcategories').where(filter=FieldFilter('category', '==', category)).stream()
    return [doc.to_dict() for doc in docs]

async def delete_subcategory(subcat_id: str):
    if not db: return False
    db.collection('subcategories').document(subcat_id).delete()
    return True

# ==========================================
# Database Functions - Shop & Products
# ==========================================
async def add_or_update_product(product_id: str, category: str, sub_category: str, name: str, price: float, delivery_type: str = "manual", stock: list = None):
    """
    🟢 UPDATED: Auto/Manual Delivery এবং Stock সংরক্ষণের অপশন যোগ করা হয়েছে
    """
    if not db: return False
    product_ref = db.collection('products').document(product_id)
    
    product_data = {
        'product_id': product_id,
        'category': category,
        'sub_category': sub_category, 
        'name': name,
        'price': float(price),
        'delivery_type': delivery_type, # "auto" or "manual"
        'stock': stock if stock else [], # অটো ডেলিভারির জন্য অ্যাকাউন্ট/কী এর লিস্ট
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    product_ref.set(product_data, merge=True)
    return True

async def get_products_by_category(category: str, sub_category: str = None):
    if not db: return {}
    query = db.collection('products').where(filter=FieldFilter('category', '==', category))
    if sub_category and sub_category != "none":
        query = query.where(filter=FieldFilter('sub_category', '==', sub_category))
    
    products = {}
    for doc in query.stream():
        products[doc.id] = doc.to_dict()
    return products

async def get_product(product_id: str):
    if not db: return None
    doc = db.collection('products').document(product_id).get()
    return doc.to_dict() if doc.exists else None

async def delete_product(product_id: str):
    if not db: return False
    db.collection('products').document(product_id).delete()
    return True

# ==========================================
# Database Functions - Pending Orders & Deposits
# ==========================================
def generate_invoice_id():
    """🟢 NEW: 랜덤 ইনভয়েস আইডি জেনারেট করবে (e.g. INV178886131)"""
    import time
    random_str = ''.join(random.choices(string.digits, k=4))
    timestamp = str(int(time.time()))
    return f"INV{timestamp}{random_str}"

async def create_pending_order(user_id: int, product_id: str, product_name: str, qty: int, total_price: float, delivery_type: str = "manual"):
    """🟢 UPDATED: ইনভয়েস আইডি এবং ডেলিভারি টাইপ সহ অর্ডার সেভ করবে"""
    if not db: return None
    
    invoice_id = generate_invoice_id()
    order_ref = db.collection('pending_orders').document(invoice_id)
    
    order_ref.set({
        'order_id': invoice_id,
        'invoice_id': invoice_id,
        'user_id': user_id,
        'product_id': product_id,
        'product_name': product_name,
        'qty': qty,
        'total_price': total_price,
        'delivery_type': delivery_type,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    })
    return invoice_id

async def create_pending_deposit(user_id: int, amount: float, method: str, sender_number: str, trx_id: str):
    if not db: return None
    deposit_ref = db.collection('pending_deposits').document()
    deposit_ref.set({
        'deposit_id': deposit_ref.id,
        'user_id': user_id,
        'amount': float(amount),
        'method': method,
        'sender_number': sender_number,
        'trx_id': trx_id,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    })
    return deposit_ref.id

# ==========================================
# Database Functions - Deposit History & Reports
# ==========================================
async def save_deposit_history(user_id: int, amount: float, method: str, trx_id: str, currency: str):
    if not db: return False
    history_ref = db.collection('deposit_history').document(trx_id)
    history_ref.set({
        'user_id': user_id,
        'amount': float(amount),
        'method': method,
        'trx_id': trx_id,
        'currency': currency,
        'timestamp': firestore.SERVER_TIMESTAMP,
    })
    return True

async def get_deposit_statement():
    if not db: return {}
    
    report = {}
    docs = db.collection('deposit_history').stream()
    
    for doc in docs:
        data = doc.to_dict()
        method_name = data.get('method', 'Unknown Method')
        amount = float(data.get('amount', 0.0))
        currency = data.get('currency', 'USDT')
        
        if method_name not in report:
            report[method_name] = {'amount': 0.0, 'currency': currency}
            
        report[method_name]['amount'] += amount
        
    return report
