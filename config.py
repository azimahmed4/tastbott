# config.py
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN") # আপনার আসল টোকেনটি এখানে দেবেন

# 🚀 আপনার বটের ইউজারনেম দিন (রেফারেল লিংকের জন্য, @ ছাড়া)
BOT_USERNAME = "TastajiBot" # (এখানে আপনার বটের ইউজারনেম বসিয়ে নেবেন)

# আপনার চ্যানেল এবং গ্রুপের ইউজারনেম
REQUIRED_CHANNELS = ["@tast1g", "@tast2g", "@tastgu"]

# Environment Variable থেকে অ্যাডমিন আইডি নেওয়া হচ্ছে
admin_id_env = os.environ.get("ADMIN_ID")

# আইডি থাকলে সেটাকে নাম্বারে (int) কনভার্ট করে লিস্টে রাখা হচ্ছে
if admin_id_env:
    ADMIN_IDS = [int(admin_id_env)]
else:
    ADMIN_IDS = [] # যদি Render-এ সেট করতে ভুলে যান, তাহলে খালি থাকবে

# 🚀 নতুন সেটিংস (আপনার লিংকগুলো এখানে বসাবেন)
YOUTUBE_LINK = "https://youtube.com/@AjimAhmed"
SUPPORT_USERNAME = "https://t.me/AjimAhmed"

# 🚀 রেফারেল বোনাস (অ্যাডমিন হিসেবে আপনি যখন খুশি এটা চেঞ্জ করতে পারবেন)
REFERRAL_BONUS = 0.05 # প্রতি রেফারে কত ডলার/টাকা পাবে তা এখানে সেট করবেন
