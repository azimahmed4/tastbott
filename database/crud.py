# database/crud.py
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# রেন্ডারের Environment Variable থেকে JSON ডাটা নেওয়া হচ্ছে
firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS")

# ডাটাবেস ইনিশিয়ালাইজেশন
db = None
if firebase_creds_json:
    try:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        
        # একাধিকবার কানেক্ট হওয়া ঠেকাতে চেক করা হচ্ছে
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            
        db = firestore.client()
        print("✅ Firebase Connected Successfully!")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")
else:
    print("⚠️ FIREBASE_CREDENTIALS not found!")

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
            referrer_doc = referrer_ref.get()
            if referrer_doc.exists:
                referrer_ref.update({
                    'total_referrals': firestore.Increment(1)
                })
        return True
    return False

async def get_user(user_id: int):
    if not db: return None
    user_ref = db.collection('users').document(str(user_id))
    doc = user_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

# ==========================================
# Database Functions - Shop & Products (No Stock)
# ==========================================

async def add_or_update_product(product_id: str, category: str, name: str, price: float):
    """স্টক ছাড়াই ক্যাটাগরিভিত্তিক প্রোডাক্ট সেভ করবে"""
    if not db: return False
    
    product_ref = db.collection('products').document(product_id)
    product_data = {
        'product_id': product_id,
        'category': category,
        'name': name,
        'price': float(price),
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    product_ref.set(product_data, merge=True)
    return True

async def get_products_by_category(category: str):
    """নির্দিষ্ট ক্যাটাগরির প্রোডাক্টগুলো আনবে"""
    if not db: return {}
    
    products = {}
    docs = db.collection('products').where(filter=FieldFilter('category', '==', category)).stream()
    for doc in docs:
        products[doc.id] = doc.to_dict()
    return products

async def get_product(product_id: str):
    if not db: return None
    product_ref = db.collection('products').document(product_id)
    doc = product_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

async def delete_product(product_id: str):
    if not db: return False
    db.collection('products').document(product_id).delete()
    return True

# ==========================================
# Database Functions - Pending Orders & Deposits
# ==========================================

async def create_pending_order(user_id: int, product_id: str, product_name: str, qty: int, total_price: float):
    """ম্যানুয়াল ডেলিভারির জন্য পেন্ডিং অর্ডার ক্রিয়েট করবে"""
    if not db: return None
    
    order_ref = db.collection('pending_orders').document()
    order_data = {
        'order_id': order_ref.id,
        'user_id': user_id,
        'product_id': product_id,
        'product_name': product_name,
        'qty': qty,
        'total_price': total_price,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    order_ref.set(order_data)
    return order_ref.id

async def create_pending_deposit(user_id: int, amount: float, method: str, sender_number: str, trx_id: str):
    """ম্যানুয়াল অ্যাপ্রুভালের জন্য ডিপোজিট রিকোয়েস্ট সেভ করবে"""
    if not db: return None
    
    deposit_ref = db.collection('pending_deposits').document()
    deposit_data = {
        'deposit_id': deposit_ref.id,
        'user_id': user_id,
        'amount': float(amount),
        'method': method,
        'sender_number': sender_number,
        'trx_id': trx_id,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    deposit_ref.set(deposit_data)
    return deposit_ref.id
