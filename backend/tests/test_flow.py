"""دورة كاملة: فاتورة ← دفعات جزئية ← تأخر ← وكيل التحصيل ← مطابقة بنكية ← PDF ← webhook ← سجل التدقيق."""
import hashlib
import hmac
import json
import os
import tempfile
from datetime import timedelta

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/t.db"
os.environ["ADMIN_PASSWORD"] = "admin-pass-123"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["WEBHOOK_SECRET"] = "whsec_test"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.models import today_om  # noqa: E402


def login(c, email="admin@company.local", pw="admin-pass-123"):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mk_invoice(c, h, cust, price, qty=1, due_in=30, issue_ago=0, issue=True):
    today = today_om()
    body = {"customer_id": cust, "issue_date": str(today - timedelta(days=issue_ago)), "due_date": str(today - timedelta(days=issue_ago) + timedelta(days=due_in)),
            "items": [{"description": "خدمات", "quantity": qty, "unit_price": price}]}
    inv = c.post("/api/invoices", json=body, headers=h).json()
    if issue:
        r = c.post(f"/api/invoices/{inv['id']}/issue", headers=h)
        assert r.status_code == 200
        inv = r.json()
    return inv


def test_full_flow():
    with TestClient(app) as c:
        h = login(c)
        c.post("/api/users", json={"name": "ناصر", "email": "nasser@x.om", "password": "pass-12345", "role": "finance"}, headers=h)
        c.post("/api/users", json={"name": "قارئ", "email": "view@x.om", "password": "pass-12345", "role": "viewer"}, headers=h)
        fin, view = login(c, "nasser@x.om", "pass-12345"), login(c, "view@x.om", "pass-12345")
        c.patch("/api/settings", json={"company_name": "شركة المثال", "bank_details": "بنك مسقط IBAN OM12 3456"}, headers=fin)
        a = c.post("/api/customers", json={"name": "شركة الخليج للتجارة", "email": "a@gulf.om", "contact_name": "سالم", "credit_days": 30}, headers=fin).json()
        b = c.post("/api/customers", json={"name": "مؤسسة نزوى للتوريدات", "email": "b@nizwa.om", "preferred_channel": "whatsapp", "phone": "99123456"}, headers=fin).json()

        # الحساب بالبيسة والضريبة 5%
        inv = mk_invoice(c, fin, a["id"], 500, qty=2)
        assert inv["total"] == 1050.0 and inv["status"] == "issued"
        assert c.post("/api/invoices", json={"customer_id": a["id"], "items": [{"description": "x", "quantity": 1, "unit_price": 10}]}, headers=view).status_code == 403

        # دفعات جزئية ورفض الدفع الزائد
        r = c.post(f"/api/invoices/{inv['id']}/payments", json={"amount": 400, "reference": "CHQ-1"}, headers=fin).json()
        assert r["status"] == "partial" and r["balance"] == 650.0
        assert c.post(f"/api/invoices/{inv['id']}/payments", json={"amount": 700}, headers=fin).status_code == 400
        r = c.post(f"/api/invoices/{inv['id']}/payments", json={"amount": 650.0, "reference": "TRF-9"}, headers=fin).json()
        assert r["status"] == "paid" and r["balance"] == 0
        assert c.post(f"/api/invoices/{inv['id']}/void", json={"reason": "خطأ"}, headers=fin).status_code == 400  # مسددة

        # PDF عربي
        pdf = c.get(f"/api/invoices/{inv['id']}/pdf", headers=fin)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

        # فاتورة متأخرة 20 يوماً ← وكيل التحصيل: تذكير + خطة تسوية، ولا تكرار
        late = mk_invoice(c, fin, a["id"], 800, due_in=30, issue_ago=50)  # استحقاق قبل 20 يوماً، 840 ر.ع
        assert c.get(f"/api/invoices/{late['id']}", headers=fin).json()["status"] == "overdue"
        res = c.post("/api/collections/run", headers=fin).json()
        assert res["reminders"] == 1 and res["plans_proposed"] == 1
        assert c.post("/api/collections/run", headers=fin).json()["reminders"] == 0
        rem = c.get("/api/reminders", headers=fin).json()[0]
        assert rem["stage"] == "d+14" and "840.000" in rem["body"] and rem["status"] == "draft"
        plan = c.get("/api/plans", headers=fin).json()[0]
        assert sum(x["amount"] for x in plan["installments"]) == 840.0 and len(plan["installments"]) == 3
        assert c.post(f"/api/plans/{plan['id']}/accept", headers=fin).json()["status"] == "active"
        # فاتورة العميل الواتساب: القناة واتساب مع رقم دولي
        wa = mk_invoice(c, fin, b["id"], 200, due_in=10, issue_ago=12)  # متأخرة يومين، 210
        c.post("/api/collections/run", headers=fin)
        wr = [r for r in c.get("/api/reminders", headers=fin).json() if r["invoice_id"] == wa["id"]]
        assert wr and wr[0]["channel"] == "whatsapp" and wr[0]["whatsapp_phone"] == "96899123456"
        # بلا SMTP: الإرسال بالبريد يفشل بوضوح ويبقى التذكير قابلاً للمحاولة
        assert c.post(f"/api/reminders/{rem['id']}/send", headers=fin).status_code == 400

        # المطابقة البنكية
        i3 = mk_invoice(c, fin, a["id"], 1000, qty=1)       # 1050
        i4 = mk_invoice(c, fin, b["id"], 300, qty=1)        # 315
        csv_body = (
            "date,amount,description,reference,counterparty\n"
            f"{today_om()},1050.000,تحويل وارد,{i3['number']},شركة الخليج للتجارة\n"      # رقم + مبلغ كامل → تلقائي
            f"{today_om()},315.000,دفعة توريد,,مؤسسة نزوى للتوريدات ش.م.م\n"             # اسم + مبلغ → مقترحة (0.88)
            f"{today_om()},77.770,إيداع غير معروف,,جهة مجهولة\n"                          # لا مطابقة
            f"{today_om()},-50.000,رسوم بنكية,,البنك\n"                                    # خصم: يُتجاهل
        )
        up = c.post("/api/bank/import", files={"file": ("b.csv", csv_body.encode(), "text/csv")}, headers=fin).json()
        assert up["imported"] == 3 and up["matched"] == 1 and up["suggested"] == 1 and up["unmatched"] == 1 and up["debits_skipped"] == 1
        assert c.post("/api/bank/import", files={"file": ("b.csv", csv_body.encode(), "text/csv")}, headers=fin).json()["duplicates"] == 3
        assert c.get(f"/api/invoices/{i3['id']}", headers=fin).json()["status"] == "paid"
        sug = [t for t in c.get("/api/bank/transactions", headers=fin).json() if t["status"] == "suggested"][0]
        assert sug["suggestion"][0]["invoice"] == i4["number"]
        assert c.post(f"/api/bank/transactions/{sug['id']}/confirm", json={}, headers=fin).json()["status"] == "matched"
        assert c.get(f"/api/invoices/{i4['id']}", headers=fin).json()["status"] == "paid"

        # webhook موقّع ومنع التكرار
        i5 = mk_invoice(c, fin, a["id"], 100)  # 105
        raw = json.dumps({"invoice_number": i5["number"], "amount": 105, "reference": "pi_123"}).encode()
        sig = hmac.new(b"whsec_test", raw, hashlib.sha256).hexdigest()
        assert c.post("/api/webhooks/payments", content=raw, headers={"X-Signature": "bad"}).status_code == 401
        assert c.post("/api/webhooks/payments", content=raw, headers={"X-Signature": sig}).json()["recorded"] is True
        assert c.post("/api/webhooks/payments", content=raw, headers={"X-Signature": sig}).json()["duplicate"] is True

        # لوحة التحكم والتقادم والمحادثة والتدقيق
        d = c.get("/api/dashboard", headers=view).json()
        assert d["overdue_count"] == 2 and d["aging"]["d1_30"] == 840.0 + 210.0
        r = c.post("/api/agents/chat", json={"agent": "dunning", "message": "ما الفواتير المتأخرة؟"}, headers=view).json()
        assert r["mode"] == "rules" and r["trace"][0]["tool"] == "overdue_invoices" and "840.000" in r["reply"]
        assert c.post("/api/agents/chat", json={"agent": "x", "message": "hi"}, headers=view).status_code == 404
        assert c.get("/api/audit/verify", headers=fin).json()["valid"] is True
        assert c.get("/api/audit/logs", headers=view).status_code == 403
