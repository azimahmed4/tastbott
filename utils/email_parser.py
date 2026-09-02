# ==========================================
# File: utils/email_parser.py
# Purpose: জিমেইল থেকে বাইনান্স এবং বাইবিটের পেমেন্ট অটো-ভেরিফাই করা (Advanced HTML Parser)
# ==========================================
import imaplib
import email
import re
import os

EMAIL_ACCOUNT = os.environ.get("GMAIL_ACCOUNT")
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

def check_crypto_payment(expected_amount: float, platform: str) -> bool:
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        print("⚠️ GMAIL_ACCOUNT or GMAIL_APP_PASSWORD missing!")
        return False

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        # 🚀 নির্দিষ্ট ইমেইলের বদলে সেন্ডারের নামে 'binance' বা 'bybit' আছে কি না সেটা খুঁজবে
        search_query = '(FROM "binance")' if platform == "binance" else '(FROM "bybit")'
        status, messages = mail.search(None, search_query)
        
        if status != "OK" or not messages[0]:
            print("⚠️ No emails found from this platform.")
            return False

        email_ids = messages[0].split()
        
        # সর্বশেষ ৫টি মেইল চেক করবে
        for e_id in email_ids[-5:]:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            # Text এবং HTML দুটোই রিড করবে
                            if content_type == "text/plain":
                                body += part.get_payload(decode=True).decode(errors="ignore")
                            elif content_type == "text/html":
                                html_body = part.get_payload(decode=True).decode(errors="ignore")
                                # HTML ট্যাগগুলো রিমুভ করে প্লেইন টেক্সট বানাবে
                                body += re.sub(r'<[^>]+>', ' ', html_body)
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                        body = re.sub(r'<[^>]+>', ' ', body)

                    # 🚀 স্ট্রং Regex লজিক (যেকোনো স্পেস বা HTML ট্যাগের পর ডাটা ধরতে পারবে)
                    if platform == "binance":
                        match = re.search(r"Amount:?\s*([0-9\.]+)\s*USDT", body, re.IGNORECASE)
                        if match:
                            found_amount = float(match.group(1))
                            if found_amount == expected_amount:
                                mail.logout()
                                return True
                    elif platform == "bybit":
                        if str(expected_amount) in body:
                            mail.logout()
                            return True

        mail.logout()
        return False

    except Exception as e:
        print(f"❌ IMAP Error: {e}")
        return False
