import os, uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

import db
from parsing import read_cv, read_job_url
from scoring import analyze

app = FastAPI(title="CV ATS Matcher")
PACK_CREDITS = int(os.getenv("PACK_CREDITS", "3"))
PACK_PRICE = float(os.getenv("PACK_PRICE", "2.05"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def current_user(authorization: str = Header("")):
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.")
    user = db.get_user(authorization[7:])
    if not user:
        raise HTTPException(401, "Your session expired. Please log in again.")
    return user


@app.get("/api/config")
def config():
    # The anon key is public by design; the service key never leaves the server.
    return {"url": db.URL, "anon": db.ANON}


@app.get("/api/credits")
def credits(user=Depends(current_user)):
    return {"credits": db.get_credits(user["id"])}


@app.post("/api/analyze")
async def analyze_ep(job_text: str = Form(""), job_url: str = Form(""), cv_text: str = Form(""),
                     cv_file: UploadFile | None = File(None), user=Depends(current_user)):
    try:
        job = job_text.strip() or (read_job_url(job_url.strip()) if job_url.strip() else "")
        cv = cv_text.strip()
        if cv_file and cv_file.filename:
            cv = read_cv(cv_file.filename, await cv_file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Could not read the input. Try pasting text instead.")
    if len(job) < 80:
        raise HTTPException(400, "Add the job description (paste the text or a link).")
    if len(cv) < 80:
        raise HTTPException(400, "Could not read enough text from your CV.")
    uid = user["id"]
    if not db.use_credit(uid):
        raise HTTPException(402, "No credits left. Buy a pack to continue.")
    try:
        res = analyze(cv, job)
    except Exception:
        db.refund(uid)
        raise HTTPException(500, "Analysis failed. Your credit was returned.")
    res["credits"] = db.get_credits(uid)
    return res


# ---- Paynow (EcoCash). Needs PAYNOW_ID and PAYNOW_KEY. ----
def _paynow():
    from paynow import Paynow
    return Paynow(os.environ["PAYNOW_ID"], os.environ["PAYNOW_KEY"],
                  f"{BASE_URL}/?paid=1", f"{BASE_URL}/api/pay/webhook")


@app.post("/api/pay")
def pay(phone: str = Form(...), user=Depends(current_user)):
    if not os.getenv("PAYNOW_ID"):
        raise HTTPException(503, "Payments are not configured yet.")
    ref = uuid.uuid4().hex[:12]
    p = _paynow()
    payment = p.create_payment(ref, user["email"])
    payment.add(f"{PACK_CREDITS} CV checks", PACK_PRICE)
    r = p.send_mobile(payment, phone, "ecocash")
    if not r.success:
        raise HTTPException(400, "Payment could not start. Check the EcoCash number.")
    db.add_payment(ref, user["id"], PACK_CREDITS, r.poll_url)
    return {"ref": ref, "instructions": r.instructions}


@app.get("/api/pay/status")
def pay_status(ref: str, user=Depends(current_user)):
    row = db.get_payment(ref)
    if not row or row["uid"] != user["id"]:
        raise HTTPException(404, "Unknown payment.")
    if not row["paid"]:
        if _paynow().check_transaction_status(row["poll"]).paid:  # verified with Paynow, not the browser
            db.mark_paid(ref)
    return {"paid": bool(db.get_payment(ref)["paid"]), "credits": db.get_credits(user["id"])}


@app.post("/api/pay/webhook")
def webhook(reference: str = Form("")):
    row = db.get_payment(reference)
    if row and not row["paid"] and _paynow().check_transaction_status(row["poll"]).paid:
        db.mark_paid(reference)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse("index.html")


