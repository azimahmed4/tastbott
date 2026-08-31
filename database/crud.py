# database/crud.py
import os
import json
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
async def add_or_update_product(product_id: str, category: str, sub_category: str, name: str, price: float):
    if not db: return False
    product_ref = db.collection('products').document(product_id)
    product_data = {
        'product_id': product_id,
        'category': category,
        'sub_category': sub_category, # নতুন ফিল্ড
        'name': name,
        'price': float(price),
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
async def create_pending_order(user_id: int, product_id: str, product_name: str, qty: int, total_price: float):
    if not db: return None
    order_ref = db.collection('pending_orders').document()
    order_ref.set({
        'order_id': order_ref.id,
        'user_id': user_id,
        'product_id': product_id,
        'product_name': product_name,
        'qty': qty,
        'total_price': total_price,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    })
    return order_ref.id

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
