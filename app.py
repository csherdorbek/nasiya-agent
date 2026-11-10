"""Nasiya agenti: Instagram webhook + menejer paneli.

Ishga tushirish:  uvicorn app:app --host 0.0.0.0 --port 8000
"""
import csv
import html
import io
import json
import logging
import os
import hashlib
import hmac
import secrets
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

import bot
import db
import messenger
from rules import DEBT_TYPES, Debt, decide

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "nasiya-verify")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "")

app = FastAPI(title="Nasiya agenti")
db.init()


# ---------------------------------------------------------------- webhook

@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verify token mos emas")


@app.post("/webhook")
async def receive(request: Request):
    body = await request.body()
    if not messenger.verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "Imzo noto'g'ri")
    data = json.loads(body or b"{}")
    for entry in data.get("entry", []):
        for ev in entry.get("messaging", []):
            msg = ev.get("message") or {}
            if msg.get("is_echo") or "text" not in msg:
                continue
            sender = ev.get("sender", {}).get("id")
            if not sender:
                continue
            before = (db.get(sender) or {}).get("status")
            for reply in bot.handle(sender, msg["text"]):
                messenger.send_instagram(sender, reply)
            after = db.get(sender)
            if after and after["status"] == "mib_tekshiruvida" and before != "mib_tekshiruvida":
                link = f"{PUBLIC_URL}/admin/check/{sender}" if PUBLIC_URL else "/admin"
                messenger.notify_manager(
                    f"Yangi nasiya arizasi: {after['full_name']}, {after['model']}, "
                    f"{after['term']} oy. MIB tekshiruvi kerak: {link}"
                )
    return {"ok": True}


# ---------------------------------------------------------------- admin

COOKIE = "nasiya_admin"


def _session_value() -> str:
    """Parolga bog'langan imzo: parol o'zgarsa, eski sessiyalar bekor bo'ladi."""
    return hmac.new(ADMIN_PASSWORD.encode(), f"{ADMIN_USER}:session".encode(), hashlib.sha256).hexdigest()


def admin(request: Request):
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "ADMIN_PASSWORD o'rnatilmagan")
    if secrets.compare_digest(request.cookies.get(COOKIE, ""), _session_value()):
        return ADMIN_USER
    raise HTTPException(303, headers={"Location": "/admin/login"})


@app.get("/admin/login", response_class=HTMLResponse)
def login_form(error: int = 0):
    msg = "<p style='color:#b42318'>Login yoki parol noto'g'ri</p>" if error else ""
    return page("Kirish", f"""
<h1>Menejer paneli</h1>{msg}
<form method=post style='max-width:320px'>
<p><label>Login<br><input name=username value='admin' style='width:100%'></label></p>
<p><label>Parol<br><input name=password type=password autofocus style='width:100%'></label></p>
<p><button class=btn>Kirish</button></p>
</form>""")


@app.post("/admin/login")
async def login_submit(request: Request):
    form = await request.form()
    ok = bool(ADMIN_PASSWORD) and secrets.compare_digest(
        str(form.get("username", "")), ADMIN_USER
    ) and secrets.compare_digest(str(form.get("password", "")), ADMIN_PASSWORD)
    if not ok:
        return RedirectResponse("/admin/login?error=1", status_code=303)
    r = RedirectResponse("/admin", status_code=303)
    r.set_cookie(COOKIE, _session_value(), httponly=True, secure=PUBLIC_URL.startswith("https"),
                 samesite="lax", max_age=30 * 86400)
    return r


@app.get("/admin/logout")
def logout():
    r = RedirectResponse("/admin/login", status_code=303)
    r.delete_cookie(COOKIE)
    return r


CSS = """
body{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#1d2433}
h1{font-size:22px}h2{font-size:17px;margin-top:28px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border-bottom:1px solid #e3e6ec;padding:8px;text-align:left;vertical-align:top}
.btn{display:inline-block;padding:8px 14px;border-radius:8px;background:#1f6feb;color:#fff;
text-decoration:none;border:0;font-size:14px;cursor:pointer}
.btn.green{background:#1a7f37}.muted{color:#6b7280}.box{background:#f5f7fa;padding:14px;border-radius:10px}
select,input{padding:6px;font-size:14px}
"""


def e(v) -> str:
    return html.escape("" if v is None else str(v))


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        f"<title>{e(title)}</title><style>{CSS}</style>{body}"
    )


def ts(v) -> str:
    return datetime.fromtimestamp(v).strftime("%d.%m %H:%M") if v else ""


@app.get("/admin", response_class=HTMLResponse)
def dashboard(_: str = Depends(admin)):
    def table(rows, with_check=False, show_decision=False):
        if not rows:
            return "<p class=muted>Hozircha yo'q</p>"
        head = "<tr><th>Vaqt</th><th>Mijoz</th><th>Telefon</th><th>Model / muddat</th>"
        head += "<th>Natija</th>" if show_decision else ""
        head += "<th></th></tr>" if with_check else "</tr>"
        out = [head]
        for r in rows:
            dec = json.loads(r["decision"]) if r["decision"] else {}
            out.append(
                f"<tr><td>{ts(r['updated_at'])}</td><td>{e(r['full_name'])}</td>"
                f"<td>{e(r['phone'])}</td><td>{e(r['model'])} · {e(r['term'])} oy</td>"
                + (f"<td>{e(dec.get('reason'))}</td>" if show_decision else "")
                + (f"<td><a class=btn href='/admin/check/{e(r['ig_id'])}'>Tekshirish</a></td>"
                   if with_check else "")
                + "</tr>"
            )
        return "<table>" + "".join(out) + "</table>"

    body = (
        "<h1>Nasiya arizalari</h1>"
        "<p><a class='btn green' href='/admin/leads.csv'>Leadlarni Excel'ga (CSV)</a> "
        "&nbsp;<a href='/admin/logout' class=muted>Chiqish</a></p>"
        "<h2>MIB tekshiruvini kutmoqda</h2>" + table(db.by_status("mib_tekshiruvida"), True)
        + "<h2>Leadlar</h2>" + table(db.by_status("lead"), show_decision=True)
        + "<h2>Rad etilganlar</h2>" + table(db.by_status("rad"), show_decision=True)
    )
    return page("Nasiya arizalari", body)


@app.get("/admin/check/{ig_id}", response_class=HTMLResponse)
def check_form(ig_id: str, _: str = Depends(admin)):
    c = db.get(ig_id)
    if not c:
        raise HTTPException(404, "Mijoz topilmadi")
    opts = "".join(
        f"<option value='{k}'>{e(v[0])} ({'undiruv' if v[1] == 'undiruv' else 'ma`muriy'})</option>"
        for k, v in DEBT_TYPES.items()
    )
    rows = "".join(
        f"<tr><td><select name=type><option value=''>—</option>{opts}</select></td>"
        f"<td><input name=amount type=number min=0 step=1000 placeholder='summa, so`m'></td></tr>"
        for _ in range(5)
    )
    body = f"""
<p><a href='/admin'>&larr; Orqaga</a></p>
<h1>{e(c['full_name'])}</h1>
<div class=box>
<b>Pasport:</b> {e(c['passport'])} &nbsp; <b>JShShIR:</b> {e(c['pinfl'])}<br>
<b>Telefon:</b> {e(c['phone'])} &nbsp; <b>Model:</b> {e(c['model'])} · {e(c['term'])} oy
</div>
<h2>1. MIB'da tekshiring</h2>
<p><a class=btn href='https://mib.uz' target=_blank rel=noopener>mib.uz'ni ochish</a>
<span class=muted>&nbsp; "Qarzdorlikni tekshirish" bo'limiga pasport yoki JShShIR'ni kiriting.</span></p>
<h2>2. Natijani kiriting</h2>
<form method=post>
<p><button class='btn green' name=none value=1>Qarz yo'q</button></p>
<p class=muted>yoki topilgan har bir qarzni tanlang:</p>
<table><tr><th>Qarz turi</th><th>Summa</th></tr>{rows}</table>
<p><button class=btn>Qaror chiqarish va mijozga yuborish</button></p>
</form>
<p class=muted>Undiruv qarzi bo'lsa — rad, sababi mijozga yoziladi. Faqat ma'muriy jarimalar
10 mln so'mgacha bo'lsa — lead.</p>"""
    return page(c["full_name"] or "Mijoz", body)


@app.post("/admin/check/{ig_id}")
async def check_submit(ig_id: str, request: Request, _: str = Depends(admin)):
    c = db.get(ig_id)
    if not c:
        raise HTTPException(404, "Mijoz topilmadi")
    form = await request.form()
    debts: list[Debt] = []
    if not form.get("none"):
        types, amounts = form.getlist("type"), form.getlist("amount")
        for t, a in zip(types, amounts):
            if not t:
                continue
            try:
                amt = int(float(a or 0))
            except ValueError:
                raise HTTPException(400, "Summa noto'g'ri")
            debts.append(Debt(t, amt))
        if not debts:
            raise HTTPException(400, "Qarz kiritilmadi. Qarz bo'lmasa, \"Qarz yo'q\" tugmasini bosing.")
    try:
        d = decide(debts)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    db.update(
        ig_id,
        state="done",
        status="lead" if d.approved else "rad",
        mib_debts=[{"code": x.code, "amount": x.amount} for x in debts],
        decision=json.dumps({"approved": d.approved, "reason": d.reason}, ensure_ascii=False),
    )
    messenger.send_instagram(ig_id, d.client_text)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/leads.csv")
def export(_: str = Depends(admin)):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Sana", "F.I.Sh", "Telefon", "Pasport", "JShShIR", "Model", "Muddat (oy)", "MIB natija"])
    for r in db.by_status("lead"):
        dec = json.loads(r["decision"]) if r["decision"] else {}
        w.writerow([ts(r["updated_at"]), r["full_name"], r["phone"], r["passport"],
                    r["pinfl"], r["model"], r["term"], dec.get("reason", "")])
    return Response("﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=leadlar.csv"})


@app.post("/admin/cleanup")
def cleanup(_: str = Depends(admin)):
    return {"o'chirildi": db.delete_stale(30)}


@app.get("/")
def health():
    return {"status": "ishlayapti"}
