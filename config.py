# config.py
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN") # আপনার আসল টোকেনটি এখানে দেবেন

# 🚀 আপনার বটের ইউজারনেম দিন (রেফারেল লিংকের জন্য, @ ছাড়া)
BOT_USERNAME = "OmniSubBot" # (এখানে আপনার বটের ইউজারনেম বসিয়ে নেবেন)

# আপনার চ্যানেল এবং গ্রুপের ইউজারনেম
REQUIRED_CHANNELS = ["@tast1g", "@omni_sub", "@OmniSubCSupport"]  


# 🚀 মাল্টিপল অ্যাডমিন সিস্টেম (কমা দিয়ে একাধিক আইডি দেওয়া যাবে)
admin_id_env = os.environ.get("ADMIN_IDS") # রেন্ডারে এনভায়রনমেন্ট ভেরিয়েবলের নাম দেবেন ADMIN_IDS

if admin_id_env:
    # যদি একাধিক আইডি থাকে, তবে কমা (,) দিয়ে ভাগ করে লিস্টে ঢুকিয়ে নেবে
    ADMIN_IDS = [int(x.strip()) for x in admin_id_env.split(",") if x.strip().isdigit()]
    print(f"✅ FINAL ADMIN_IDS লিস্ট: {ADMIN_IDS}")
else:
    print("⚠️ ADMIN_IDS খুঁজে পায়নি! এলস (else) ব্লকে চলে যাচ্ছে।")
    ADMIN_IDS = [] # যদি Render-এ সেট করতে ভুলে যান, তাহলে খালি থাকব 
    




# 🚀 নতুন সেটিংস (আপনার লিংকগুলো এখানে বসাবেন)
YOUTUBE_LINK = "https://youtube.com/@AjimAhmed"
SUPPORT_USERNAME = "https://t.me/OmniSub_Support"

# 🚀 রেফারেল বোনাস (অ্যাডমিন হিসেবে আপনি যখন খুশি এটা চেঞ্জ করতে পারবেন)
REFERRAL_BONUS = 0.05 # প্রতি রেফারে কত ডলার/টাকা পাবে তা এখানে সেট করবেন
