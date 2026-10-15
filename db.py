"""Supabase access over plain HTTPS (no extra libraries)."""
import os

import requests

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
ANON = os.getenv("SUPABASE_ANON_KEY", "")
SERVICE = os.getenv("SUPABASE_SERVICE_KEY", "")  # secret: backend only, never sent to browsers


def _h():
    h = {"apikey": SERVICE, "Content-Type": "application/json"}
    if not SERVICE.startswith("sb_"):  # legacy JWT service_role keys also go in Authorization
        h["Authorization"] = f"Bearer {SERVICE}"
    return h


def _rpc(name: str, payload: dict):
    r = requests.post(f"{URL}/rest/v1/rpc/{name}", headers=_h(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json() if r.text else None


def get_user(token: str):
    """Ask Supabase who owns this login token. Returns {'id','email'} or None."""
    try:
        r = requests.get(f"{URL}/auth/v1/user", timeout=10,
                         headers={"apikey": ANON, "Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            d = r.json()
            return {"id": d["id"], "email": d.get("email", "")}
    except requests.RequestException:
        pass
    return None


def get_credits(uid): return int(_rpc("get_credits", {"p_uid": uid}))
def use_credit(uid): return bool(_rpc("use_credit", {"p_uid": uid}))
def refund(uid): _rpc("refund_credit", {"p_uid": uid})
def mark_paid(ref): return bool(_rpc("grant_payment", {"p_ref": ref}))


def add_payment(ref, uid, credits, poll):
    r = requests.post(f"{URL}/rest/v1/payments", headers=_h(), timeout=15,
                      json={"ref": ref, "uid": uid, "credits": credits, "poll": poll})
    r.raise_for_status()


def get_payment(ref):
    r = requests.get(f"{URL}/rest/v1/payments", headers=_h(), timeout=15,
                     params={"ref": f"eq.{ref}", "select": "uid,credits,paid,poll"})
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None
