import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["ADMIN_PASSWORD"] = "parol"
os.environ.pop("IG_ACCESS_TOKEN", None)

from fastapi.testclient import TestClient  # noqa: E402

import app as appmod  # noqa: E402
import db  # noqa: E402
from rules import Debt, decide  # noqa: E402

sent: list[tuple[str, str]] = []
appmod.messenger.send_instagram = lambda rid, t: sent.append((rid, t)) or True
client = TestClient(appmod.app)
AUTH = ("admin", "parol")


# ---------- qoidalar

def test_no_debt_is_lead():
    assert decide([]).approved


def test_enforcement_debt_rejected_with_reason():
    d = decide([Debt("kredit", 2_500_000)])
    assert not d.approved
    assert "bank krediti" in d.client_text and "2 500 000" in d.client_text


def test_admin_fine_up_to_10mln_is_lead():
    assert decide([Debt("yol_jarima", 6_000_000), Debt("mamuriy", 4_000_000)]).approved


def test_admin_fine_over_10mln_rejected():
    d = decide([Debt("yol_jarima", 10_000_001)])
    assert not d.approved and "10 mln" in d.client_text


def test_small_enforcement_plus_fine_still_rejected():
    assert not decide([Debt("mamuriy", 100_000), Debt("kommunal", 50_000)]).approved


# ---------- suhbat va webhook

def say(uid, text):
    sent.clear()
    payload = {"entry": [{"messaging": [{"sender": {"id": uid}, "message": {"text": text}}]}]}
    r = client.post("/webhook", content=json.dumps(payload))
    assert r.status_code == 200
    return [t for _, t in sent]


def run_full_dialog(uid):
    say(uid, "salom")
    say(uid, "iPhone 15 128GB")
    assert "Roziman" in say(uid, "12")[0]
    say(uid, "Roziman")
    say(uid, "Aliyev Vali")
    assert "Format" in say(uid, "AD12")[0]
    say(uid, "ad 1234567")
    assert "14" in say(uid, "123")[0]
    say(uid, "31234567890123")
    assert "qabul qilindi" in say(uid, "90 123 45 67")[0]
    c = db.get(uid)
    assert c["status"] == "mib_tekshiruvida"
    assert c["passport"] == "AD1234567" and c["phone"] == "+998901234567"


def test_webhook_verify():
    r = client.get("/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "nasiya-verify", "hub.challenge": "42"})
    assert r.text == "42"


def test_flow_to_lead():
    run_full_dialog("u1")
    assert client.get("/admin", auth=AUTH).status_code == 200
    sent.clear()
    r = client.post("/admin/check/u1", data={"none": "1"}, auth=AUTH, follow_redirects=False)
    assert r.status_code == 303
    assert db.get("u1")["status"] == "lead"
    assert "qabul qilindi" in sent[-1][1]
    csv_text = client.get("/admin/leads.csv", auth=AUTH).text
    assert "AD1234567" in csv_text


def test_flow_to_reject():
    run_full_dialog("u2")
    sent.clear()
    client.post("/admin/check/u2", data={"type": ["aliment", "", "", "", ""],
                                         "amount": ["3000000", "", "", "", ""]},
                auth=AUTH, follow_redirects=False)
    assert db.get("u2")["status"] == "rad"
    assert "aliment" in sent[-1][1]


def test_fine_under_limit_lead():
    run_full_dialog("u3")
    client.post("/admin/check/u3", data={"type": ["yol_jarima", "", "", "", ""],
                                         "amount": ["800000", "", "", "", ""]},
                auth=AUTH, follow_redirects=False)
    assert db.get("u3")["status"] == "lead"


def test_no_consent():
    say("u4", "salom"); say("u4", "Redmi"); say("u4", "6")
    say("u4", "yo'q")
    assert db.get("u4")["status"] == "rozilik_yoq"


def test_admin_requires_password():
    assert client.get("/admin").status_code == 401
