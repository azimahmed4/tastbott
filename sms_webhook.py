# ==========================================
# File: sms_webhook.py
# Purpose: Receive SMS from Android App, Parse TrxID/Amount, Save to Firestore
# ==========================================
import re
from fastapi import FastAPI, Request
from firebase_admin import firestore
from database.crud import db

app = FastAPI(title="OmniSub SMS Webhook")

# 🟢 NEW: UptimeRobot/Cron-job Ping Endpoint (To keep Render 24/7 Awake)
@app.api_route("/", methods=["GET", "HEAD", "POST", "OPTIONS"])
async def root_ping():
    return {"status": "Alive", "message": "OmniSub SMS Webhook is running 24/7!"}

@app.post("/webhook/sms")
async def receive_sms(request: Request):
    try:
        data = await request.json()
        sender = data.get("sender", "").strip().lower()
        message = data.get("message", "").strip()
        
        # ১. শুধুমাত্র অনুমোদিত গেটওয়ে থেকে মেসেজ রিসিভ করবে
        allowed_senders = ["bkash", "nagad", "rocket"]
        if not any(allowed in sender for allowed in allowed_senders):
            return {"status": "ignored", "reason": "Not a valid payment gateway."}

        # ২. রেজেক্স (Regex) দিয়ে TrxID এবং Amount বের করা (100% Accurate)
        # bKash/Nagad/Rocket এর SMS ফরম্যাট অনুযায়ী
        trx_match = re.search(r'(?:TrxID|TxnID)\s*[:\-]?\s*([A-Za-z0-9]+)', message, re.IGNORECASE)
        amount_match = re.search(r'Tk\s*[:\-]?\s*([\d\.,]+)', message, re.IGNORECASE)

        if trx_match and amount_match:
            trx_id = trx_match.group(1).strip()
            amount_str = amount_match.group(1).replace(',', '')
            amount = float(amount_str)
            
            if not db:
                return {"status": "error", "reason": "Database connection failed."}

            # ৩. ফায়ারবেসে ডুপ্লিকেট চেক করে সেভ করা
            doc_ref = db.collection('live_sms_payments').document(trx_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                doc_ref.set({
                    'trx_id': trx_id,
                    'amount': amount,
                    'platform': sender,
                    'is_used': False, # বট ভেরিফাই করলে এটা True হবে
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'raw_message': message # ফিউচার রেফারেন্সের জন্য
                })
                print(f"✅ [WEBHOOK SUCCESS] {sender.upper()}: {amount} BDT | TrxID: {trx_id}")
                return {"status": "success", "trx_id": trx_id, "amount": amount}
            else:
                return {"status": "ignored", "reason": "Duplicate SMS"}
                
        return {"status": "failed", "reason": "Could not parse TrxID or Amount from message."}

    except Exception as e:
        return {"status": "error", "message": str(e)}
