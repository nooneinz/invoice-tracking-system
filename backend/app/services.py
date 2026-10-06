import hashlib
import json
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import (AuditLog, Customer, Invoice, InvoiceItem, Payment, Setting, User, fm, now_om, today_om)

ROLE_LABELS = {"admin": "مشرف النظام", "finance": "المحاسبة والتحصيل", "viewer": "اطلاع فقط"}
WRITE_ROLES = ("admin", "finance")

DEFAULT_SETTINGS = {
    "company_name": "اسم شركتك", "company_vatin": "", "company_address": "مسقط، سلطنة عُمان",
    "company_phone": "", "company_email": "", "bank_details": "",
    "vat_rate": "5", "default_credit_days": "30",
    "dunning_offsets": "-3,0,7,14,30",  # أيام نسبةً إلى تاريخ الاستحقاق
    "auto_send": "0",  # 1 = تُرسل التذكيرات الودية تلقائياً عند ضبط SMTP
    "auto_reconcile": "1", "auto_threshold": "0.9",
}


# ---------- المصادقة ----------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    exp = datetime.utcnow().timestamp() + config.JWT_HOURS * 3600
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, config.JWT_SECRET, algorithm="HS256")


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "غير مصرح")
    try:
        data = jwt.decode(authorization[7:], config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "انتهت الجلسة، سجّل الدخول من جديد")
    user = db.get(User, int(data["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "الحساب غير فعّال")
    return user


def require_roles(*roles):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "لا تملك صلاحية لهذا الإجراء")
        return user
    return dep


# ---------- سجل التدقيق ----------
def _digest(prev, ts, user_id, action, entity, entity_id, details) -> str:
    return hashlib.sha256(json.dumps([prev, ts.isoformat(), user_id, action, entity, entity_id, details], ensure_ascii=False).encode()).hexdigest()


def audit(db: Session, user: User | None, action: str, entity: str = "", entity_id: int | None = None, details: str = "", actor: str = ""):
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else ""
    ts = now_om()
    db.add(AuditLog(ts=ts, user_id=user.id if user else None, user_name=actor or (user.name if user else "النظام"), action=action,
                    entity=entity, entity_id=entity_id, details=details, prev_hash=prev,
                    hash=_digest(prev, ts, user.id if user else None, action, entity, entity_id, details)))
    db.flush()


def verify_audit_chain(db: Session) -> dict:
    prev, n = "", 0
    for r in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        if r.prev_hash != prev or r.hash != _digest(prev, r.ts, r.user_id, r.action, r.entity, r.entity_id, r.details):
            return {"valid": False, "broken_at": r.id, "checked": n}
        prev, n = r.hash, n + 1
    return {"valid": True, "checked": n}


# ---------- الإعدادات ----------
def ensure_settings(db: Session):
    for k, v in DEFAULT_SETTINGS.items():
        if not db.get(Setting, k):
            db.add(Setting(key=k, value=v))
    db.flush()


def get_settings(db: Session) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update({r.key: r.value for r in db.execute(select(Setting)).scalars()})
    return s


# ---------- الفواتير والحسابات (بالبيسة) ----------
def recalc(inv: Invoice):
    sub = sum(round(i.quantity * i.unit_price) for i in inv.items)
    vat = round(sub * inv.vat_rate / 100)
    inv.subtotal, inv.vat_amount, inv.total = sub, vat, sub + vat


def balance(inv: Invoice) -> int:
    return inv.total - inv.paid


def is_overdue(inv: Invoice, today: date | None = None) -> bool:
    return inv.status in ("issued", "partial") and inv.due_date < (today or today_om())


def days_overdue(inv: Invoice, today: date | None = None) -> int:
    return max(0, ((today or today_om()) - inv.due_date).days) if inv.status in ("issued", "partial") else 0


def display_status(inv: Invoice) -> str:
    return "overdue" if is_overdue(inv) else inv.status


def next_invoice_number(db: Session) -> str:
    year = today_om().year
    n = db.execute(select(func.count(Invoice.id)).where(Invoice.number.like(f"INV-{year}-%"))).scalar() + 1
    return f"INV-{year}-{n:04d}"


def apply_payment(db: Session, inv: Invoice, amount: int, method: str, reference: str | None, received: date, source: str,
                  user_name: str, bank_txn_id: int | None = None, note: str = "") -> Payment:
    """يسجّل دفعة داخل المعاملة الحالية؛ يرفض الدفع الزائد ويُغلق الفاتورة عند السداد الكامل."""
    if inv.status not in ("issued", "partial"):
        raise HTTPException(400, "الفاتورة غير مفتوحة للسداد")
    if amount <= 0:
        raise HTTPException(400, "المبلغ يجب أن يكون أكبر من صفر")
    if amount > balance(inv):
        raise HTTPException(400, f"المبلغ ({fm(amount):,.3f}) أكبر من المتبقي ({fm(balance(inv)):,.3f} ر.ع)")
    p = Payment(invoice_id=inv.id, amount=amount, method=method, reference=reference or None, received_at=received, source=source,
                bank_txn_id=bank_txn_id, note=note, created_by=user_name)
    db.add(p)
    inv.paid += amount
    inv.payments.append(p)
    if inv.paid >= inv.total:
        inv.status, inv.closed_at = "paid", now_om()
    else:
        inv.status = "partial"
    db.flush()
    return p


# ---------- سلوك العميل ----------
def customer_stats(db: Session, customer_id: int) -> dict:
    invs = list(db.execute(select(Invoice).where(Invoice.customer_id == customer_id, Invoice.status != "void", Invoice.status != "draft")).scalars())
    today = today_om()
    late_days, late_count, paid_count = [], 0, 0
    for i in invs:
        if i.status == "paid" and i.payments:
            paid_count += 1
            last = max(p.received_at for p in i.payments)
            d = (last - i.due_date).days
            if d > 0:
                late_days.append(d)
                late_count += 1
    open_over = [i for i in invs if is_overdue(i, today)]
    return {"invoices": len(invs), "paid_invoices": paid_count, "late_count": late_count,
            "avg_days_late": round(sum(late_days) / len(late_days), 1) if late_days else 0,
            "open_overdue": len(open_over), "overdue_amount": sum(balance(i) for i in open_over),
            "outstanding": sum(balance(i) for i in invs if i.status in ("issued", "partial"))}


def aging(db: Session, today: date | None = None) -> dict:
    today = today or today_om()
    b = {"current": 0, "d1_30": 0, "d31_60": 0, "d61_90": 0, "d90_plus": 0}
    for i in db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial"]))).scalars():
        d = (today - i.due_date).days
        k = "current" if d <= 0 else "d1_30" if d <= 30 else "d31_60" if d <= 60 else "d61_90" if d <= 90 else "d90_plus"
        b[k] += balance(i)
    return {k: fm(v) for k, v in b.items()}


# ---------- PDF ----------
_FONT_CANDIDATES = ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
_BOLD_CANDIDATES = ["C:/Windows/Fonts/tahomabd.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]


def _ar(text: str) -> str:
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(str(text)))


def invoice_pdf(inv: Invoice, s: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    reg = next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)
    bold = next((p for p in _BOLD_CANDIDATES if Path(p).exists()), reg)
    if not reg:
        raise HTTPException(500, "لا يوجد خط يدعم العربية على الخادم لتوليد PDF")
    if "TahseelReg" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TahseelReg", reg))
        pdfmetrics.registerFont(TTFont("TahseelBold", bold))
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    R, L = W - 40, 40
    maroon, ink, grey = colors.HexColor("#7b1e2e"), colors.HexColor("#1b1f27"), colors.HexColor("#5b6472")

    def txt(x, y, t, size=10, bold_=False, color=ink, align="r"):
        c.setFont("TahseelBold" if bold_ else "TahseelReg", size)
        c.setFillColor(color)
        t = _ar(t)
        (c.drawRightString if align == "r" else c.drawString if align == "l" else c.drawCentredString)(x, y, t)

    c.setFillColor(maroon); c.rect(0, H - 14, W, 14, stroke=0, fill=1)
    txt(R, H - 60, s["company_name"], 18, True, maroon)
    y = H - 78
    for line in [s["company_address"], f"الرقم الضريبي: {s['company_vatin']}" if s["company_vatin"] else "", s["company_phone"], s["company_email"]]:
        if line:
            txt(R, y, line, 9, color=grey); y -= 13
    txt(L, H - 60, "فاتورة ضريبية" if inv.vat_rate else "فاتورة", 18, True, ink, "l")
    txt(L, H - 80, inv.number, 11, True, maroon, "l")
    y = min(y, H - 120) - 14
    c.setStrokeColor(colors.HexColor("#d9dde3")); c.line(L, y + 8, R, y + 8)
    txt(R, y - 6, "العميل", 9, color=grey); txt(R, y - 21, inv.customer.name, 12, True)
    ly = y - 36
    for line in [f"الرقم الضريبي: {inv.customer.vatin}" if inv.customer.vatin else "", inv.customer.address]:
        if line:
            txt(R, ly, line, 9, color=grey); ly -= 13
    txt(L + 200, y - 6, "تاريخ الإصدار", 9, color=grey, align="l"); txt(L + 200, y - 21, inv.issue_date.isoformat(), 11, align="l")
    txt(L, y - 6, "تاريخ الاستحقاق", 9, color=grey, align="l"); txt(L, y - 21, inv.due_date.isoformat(), 11, True, maroon, "l")
    y = ly - 20
    c.setFillColor(colors.HexColor("#f1f2f4")); c.rect(L, y - 4, R - L, 20, stroke=0, fill=1)
    cols = {"desc": R - 8, "qty": R - 270, "price": R - 340, "total": L + 8}
    txt(cols["desc"], y + 2, "الوصف", 9, True); txt(cols["qty"], y + 2, "الكمية", 9, True, align="c"); txt(cols["price"], y + 2, "سعر الوحدة", 9, True, align="c"); txt(cols["total"], y + 2, "الإجمالي", 9, True, align="l")
    y -= 22
    for it in inv.items:
        txt(cols["desc"], y, it.description[:60], 10)
        txt(cols["qty"], y, f"{it.quantity:g}", 10, align="c"); txt(cols["price"], y, f"{fm(it.unit_price):,.3f}", 10, align="c")
        txt(cols["total"], y, f"{fm(round(it.quantity * it.unit_price)):,.3f}", 10, align="l")
        c.setStrokeColor(colors.HexColor("#eceef1")); c.line(L, y - 6, R, y - 6)
        y -= 20
    y -= 8
    for label, val, strong in [("المجموع قبل الضريبة", inv.subtotal, False), (f"ضريبة القيمة المضافة ({inv.vat_rate:g}%)", inv.vat_amount, False), ("الإجمالي (ر.ع)", inv.total, True)]:
        txt(R - 150, y, label, 10, strong); txt(L + 100, y, f"{fm(val):,.3f}", 11 if strong else 10, strong, maroon if strong else ink, "l"); y -= 18
    if inv.paid:
        txt(R - 150, y, "المدفوع", 10); txt(L + 100, y, f"{fm(inv.paid):,.3f}", 10, align="l"); y -= 16
        txt(R - 150, y, "المتبقي", 10, True); txt(L + 100, y, f"{fm(balance(inv)):,.3f}", 11, True, maroon, "l"); y -= 16
    y -= 14
    for title, body in [("بيانات الدفع", s["bank_details"]), ("ملاحظات", inv.notes)]:
        if body:
            txt(R, y, title, 9, True, grey); y -= 14
            for ln in str(body).splitlines():
                txt(R, y, ln[:90], 9); y -= 12
            y -= 6
    txt(W / 2, 30, f"{inv.number} — صدرت بتوقيت مسقط", 8, color=grey, align="c")
    c.showPage(); c.save()
    return buf.getvalue()


# ---------- البريد ----------
def smtp_ready() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def send_email(to: str, subject: str, body: str, attach: tuple[str, bytes] | None = None):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, to, subject
    msg.set_content(body)
    if attach:
        msg.add_attachment(attach[1], maintype="application", subtype="pdf", filename=attach[0])
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)
