# database/dummy_db.py

# রিয়েল ডেলিভারি ডেটার জন্য 'data' ফিল্ড যুক্ত করা হলো
PRODUCTS = {
    "prod_1": {"name": "Gemini Pro 18M", "price": 0.5, "stock": 0, "data": []},
    "prod_2": {"name": "Nord VPN 3M", "price": 2.8, "stock": 3, "data": ["nord_key_1", "nord_key_2", "nord_key_3"]},
    "prod_3": {"name": "Netflix 1 Month Premium", "price": 2.5, "stock": 2, "data": ["netflix_account_1", "netflix_account_2"]}
}

USER_BALANCES = {}
USER_SPENT = {}
USER_ORDERS = {}
PENDING_DEPOSITS = {}

# 🚀 রেফারেল সিস্টেমের জন্য নতুন ডাটাবেস
REFERRED_BY = {} # কে কাকে ইনভাইট করেছে তার হিসাব
USER_REFERRALS = {} # একজন মোট কয়টা রেফার করেছে তার হিসাব