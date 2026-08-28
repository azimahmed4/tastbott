import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

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
    """নতুন ইউজার ডাটাবেসে সেভ করবে এবং ডিফল্ট ব্যালেন্স ০ সেট করবে। রেফারেল থাকলে সেটাও কাউন্ট করবে।"""
    if not db: return False
    
    user_ref = db.collection('users').document(str(user_id))
    doc = user_ref.get()
    
    if not doc.exists:
        # ইউজারের ডিফল্ট প্রোফাইল তৈরি
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'balance': 0.0,  # ডিফল্ট ব্যালেন্স জিরো
            'total_referrals': 0,
            'referred_by': str(referred_by) if referred_by else None,
            'joined_at': firestore.SERVER_TIMESTAMP
        }
        user_ref.set(user_data)
        
        # যদি কেউ রেফার করে থাকে, তবে তার রেফারেল কাউন্ট ১ বাড়িয়ে দেওয়া
        if referred_by and str(referred_by) != str(user_id):
            referrer_ref = db.collection('users').document(str(referred_by))
            referrer_doc = referrer_ref.get()
            if referrer_doc.exists:
                referrer_ref.update({
                    'total_referrals': firestore.Increment(1)
                })
        return True # নতুন ইউজার হিসেবে সেভ হয়েছে
    return False # ইউজার আগে থেকেই ডাটাবেসে আছে

async def get_user(user_id: int):
    """ইউজারের প্রোফাইল এবং ব্যালেন্স ডাটাবেস থেকে আনবে।"""
    if not db: return None
    
    user_ref = db.collection('users').document(str(user_id))
    doc = user_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    return None

# ==========================================
# Database Functions - Shop & Products
# ==========================================

async def add_or_update_product(product_id: str, name: str, price: float, stock: int, description: str = ""):
    """অ্যাডমিন প্যানেল থেকে নতুন প্রোডাক্ট ডাটাবেসে সেভ বা আপডেট করবে।"""
    if not db: return False
    
    product_ref = db.collection('products').document(product_id)
    product_data = {
        'product_id': product_id,
        'name': name,
        'price': float(price),
        'stock': int(stock),
        'description': description,
        'updated_at': firestore.SERVER_TIMESTAMP
    }
    product_ref.set(product_data, merge=True)
    return True

async def get_all_products():
    """শপে দেখানোর জন্য ডাটাবেস থেকে সব প্রোডাক্টের লিস্ট আনবে।"""
    if not db: return {}
    
    products = {}
    docs = db.collection('products').stream()
    for doc in docs:
        products[doc.id] = doc.to_dict()
    return products

async def get_product(product_id: str):
    """নির্দিষ্ট একটি প্রোডাক্টের বিস্তারিত ডাটাবেস থেকে আনবে।"""
    if not db: return None
    
    product_ref = db.collection('products').document(product_id)
    doc = product_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    return None

async def update_stock(product_id: str, quantity: int):
    """কেউ প্রোডাক্ট কিনলে ডাটাবেস থেকে স্টক মাইনাস করবে (quantity নেগেটিভ পাঠাতে হবে)।"""
    if not db: return False
    
    product_ref = db.collection('products').document(product_id)
    product_ref.update({
        'stock': firestore.Increment(quantity)
    })
    return True

async def delete_product(product_id: str):
    """অ্যাডমিন চাইলে প্রোডাক্ট ডিলিট করতে পারবে।"""
    if not db: return False
    db.collection('products').document(product_id).delete()
    return True
