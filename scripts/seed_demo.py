"""تعبئة بيانات تجريبية محلية: عملاء ومستخدمون بأدوار مختلفة، ومع --sample-data فواتير ودفعات وكشف بنكي ليرى المراجع اللوحات والوكلاء تعمل.

للتجربة المحلية فقط — يرفض العمل على سيرفر غير محلي إلا مع --allow-remote.
الاستخدام (والخادم يعمل):  python scripts/seed_demo.py [--sample-data]
يقرأ حساب المشرف من backend/.env (ADMIN_EMAIL / ADMIN_PASSWORD) أو من متغيرات البيئة.
عملاء التجربة بريدهم من النطاق المحجوز example.com حتى لا تصل رسالة لأحد بالخطأ.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

DEMO_PASSWORD = "Demo@2026"

CUSTOMERS = [
    ("شركة الخليج للتجارة ش.م.م", "accounts@gulf-trading.example.com", "سالم البلوشي", 30),
    ("مؤسسة نزوى للتوريدات", "finance@nizwa-supplies.example.com", "ناصر الراشدي", 45),
    ("شركة صلالة للمقاولات", "accounts@salalah-contracting.example.com", "خالد المعشني", 30),
    ("شركة ظفار للأغذية", "ap@dhofar-foods.example.com", "مريم الكثيري", 60),
    ("مؤسسة الباطنة للخدمات اللوجستية", "billing@batinah-logistics.example.com", "حمد الغافري", 30),
]
USERS = [("سعيد المنذري", "said.mundhiri@company.om", "finance"), ("خليل الكلباني", "khalil.kalbani@company.om", "viewer")]


def load_env() -> dict:
    env = dict(os.environ)
    f = Path(__file__).resolve().parent.parent / "backend" / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8002")
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--sample-data", action="store_true", help="أضف فواتير ودفعات وحركات بنكية تجريبية")
    a = ap.parse_args()
    if urlparse(a.base).hostname not in ("127.0.0.1", "localhost") and not a.allow_remote:
        sys.exit("رفض التنفيذ: هذا السكربت للتجربة المحلية فقط. استخدم --allow-remote إن كنت متأكداً.")
    env = load_env()
    if not env.get("ADMIN_PASSWORD"):
        sys.exit("اضبط ADMIN_PASSWORD في backend/.env ثم شغّل الخادم أولاً.")

    def call(path, body=None, token=None, method=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(a.base + "/api" + path, method=method or ("POST" if data is not None else "GET"), data=data,
                                     headers={"Content-Type": "application/json; charset=utf-8", **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return None
            raise SystemExit(f"{path}: {e.code} {e.read().decode()[:200]}")

    tok = call("/auth/login", {"email": env.get("ADMIN_EMAIL", "admin@company.local"), "password": env["ADMIN_PASSWORD"]})["token"]
    call("/settings", {"company_name": "شركة الأفق للحلول التقنية ش.م.م", "company_address": "مسقط، سلطنة عُمان",
                       "bank_details": "البنك: (أضف اسم البنك)\nIBAN: (أضفه من الإعدادات)"}, tok, "PATCH")
    for name, email, contact, days in CUSTOMERS:
        call("/customers", {"name": name, "email": email, "contact_name": contact, "credit_days": days, "preferred_channel": "email"}, tok)
    for name, email, role in USERS:
        call("/users", {"name": name, "email": email, "password": DEMO_PASSWORD, "role": role}, tok)

    if a.sample_data:
        custs = {c["name"]: c["id"] for c in call("/customers", token=tok)}
        if call("/invoices", token=tok):
            print("توجد فواتير مسبقاً؛ تُخطّى البيانات النموذجية.")
        else:
            today = date.today()

            def inv(customer, price, qty, issue_ago, credit, pay=0):
                issue = today - timedelta(days=issue_ago)
                body = {"customer_id": custs[customer], "issue_date": str(issue), "due_date": str(issue + timedelta(days=credit)),
                        "items": [{"description": "خدمات وتوريدات", "quantity": qty, "unit_price": price}]}
                i = call("/invoices", body, tok)
                i = call(f"/invoices/{i['id']}/issue", {}, tok)
                if pay:
                    call(f"/invoices/{i['id']}/payments", {"amount": pay, "reference": "CHQ-DEMO"}, tok)
                return i
            names = list(custs)
            a1 = inv(names[0], 500, 2, 70, 30, pay=1050)   # مسددة
            inv(names[0], 800, 1, 50, 30)                    # متأخرة 20 يوماً (840)
            inv(names[1], 300, 1, 40, 30)                    # متأخرة 10 أيام (315)
            inv(names[2], 1200, 1, 75, 30, pay=500)          # جزئية ومتأخرة 45 يوماً
            inv(names[3], 650, 1, 10, 60)                    # جارية
            i6 = inv(names[4], 200, 1, 5, 30)                # جارية (210)
            stmt = (f"date,amount,description,reference,counterparty\n"
                    f"{today},210.000,تحويل وارد,{i6['number']},مؤسسة الباطنة للخدمات اللوجستية\n"
                    f"{today},315.000,دفعة توريد,,مؤسسة نزوى للتوريدات ش.م.م\n"
                    f"{today},77.770,إيداع غير معروف,,جهة مجهولة\n")
            boundary = "----seed"
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"stmt.csv\"\r\nContent-Type: text/csv\r\n\r\n{stmt}\r\n--{boundary}--\r\n").encode("utf-8")
            req = urllib.request.Request(a.base + "/api/bank/import", data=body, method="POST",
                                         headers={"Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
            with urllib.request.urlopen(req) as r:
                print("المطابقة البنكية:", json.loads(r.read()))
            print("وكيل التحصيل:", call("/collections/run", {}, tok))
    print("تمت التعبئة. حسابات التجربة (كلمة المرور لكلٍّ منها):", DEMO_PASSWORD)
    for name, email, role in USERS:
        print(f"  {email:34} {role}")


if __name__ == "__main__":
    main()
