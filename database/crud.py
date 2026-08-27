import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# রেন্ডারের Environment Variable থেকে JSON ডাটা নেওয়া হচ্ছে
firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS")

# ডাটাবেস ইনিশিয়ালাইজেশন
db = None
if firebase_creds_json:
    try:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        
        # একাধিকবার কানেক্ট হওয়া ঠেকাতে চেক করা হচ্ছে
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            
        db = firestore.client()
        print("✅ Firebase Connected Successfully!")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")
else:
    print("⚠️ FIREBASE_CREDENTIALS not found!")

# ==========================================
# Database Functions
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
        
        # যদি কেউ রেফার করে থাকে, তবে তার রেফারেল কাউন্ট ১ বাড়িয়ে দেওয়া
        if referred_by and str(referred_by) != str(user_id):
            referrer_ref = db.collection('users').document(str(referred_by))
            referrer_doc = referrer_ref.get()
            if referrer_doc.exists:
                referrer_ref.update({
                    'total_referrals': firestore.Increment(1)
                })
        return True # নতুন ইউজার হিসেবে সেভ হয়েছে
    return False # ইউজার আগে থেকেই ডাটাবেসে আছে

async def get_user(user_id: int):
    """ইউজারের প্রোফাইল এবং ব্যালেন্স ডাটাবেস থেকে আনবে।"""
    if not db: return None
    
    user_ref = db.collection('users').document(str(user_id))
    doc = user_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    return None
