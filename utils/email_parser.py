# ==========================================
# File: utils/email_parser.py
# Purpose: জিমেইল থেকে বাইনান্স এবং বাইবিটের পেমেন্ট অটো-ভেরিফাই করা
# ==========================================
import imaplib
import email
import re
import os

# Render-এর Environment Variable থেকে জিমেইল এবং App Password নিয়ে আসবে
EMAIL_ACCOUNT = os.environ.get("GMAIL_ACCOUNT")
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

def check_crypto_payment(expected_amount: float, platform: str) -> bool:
    """জিমেইলে ঢুকে নির্দিষ্ট অ্যামাউন্টের ট্রানজেকশন খুঁজবে"""
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        print("⚠️ GMAIL_ACCOUNT or GMAIL_APP_PASSWORD not found in ENV variables!")
        return False

    try:
        # Gmail এর IMAP সার্ভারে লগইন
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        # প্ল্যাটফর্ম অনুযায়ী সেন্ডার ইমেইল সেট করা
        if platform == "binance":
            sender_email = "do-not-reply@ses.binance.com"
        else:
            sender_email = "no-reply@bybit.com"

        # ইনবক্স থেকে শুধু ওই সেন্ডারের মেইলগুলো খুঁজবে
        status, messages = mail.search(None, f'(FROM "{sender_email}")')
        if status != "OK" or not messages[0]:
            return False

        email_ids = messages[0].split()
        
        # স্পিড বাড়ানোর জন্য শুধু সর্বশেষ ৫টি মেইল চেক করবে
        for e_id in email_ids[-5:]:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")

                    # Regex দিয়ে অ্যামাউন্ট খোঁজার লজিক
                    if platform == "binance":
                        # খুঁজবে: "Amount: 5.07 USDT"
                        match = re.search(r"Amount:\s*([0-9\.]+)\s*USDT", body, re.IGNORECASE)
                        if match:
                            found_amount = float(match.group(1))
                            if found_amount == expected_amount:
                                mail.logout()
                                return True
                    elif platform == "bybit":
                        # বাইবিটের জন্য সাধারণ ম্যাচিং
                        if str(expected_amount) in body:
                            mail.logout()
                            return True

        mail.logout()
        return False

    except Exception as e:
        print(f"❌ IMAP Error: {e}")
        return False
