import hashlib
import hmac
from datetime import date, datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import config, jobs
from .agents import ai_enabled, apply_allocations, import_bank_csv, reconcile_txn, run_dunning
from .db import Base, engine, get_db, SessionLocal
from .models import (ROLES, AuditLog, BankTransaction, Customer, Invoice, InvoiceItem, JobRun, Payment, Reminder, Setting,
                     SettlementPlan, User, fm, now_om, to_b, today_om)
from .services import (DEFAULT_SETTINGS, ROLE_LABELS, WRITE_ROLES, aging, apply_payment, audit, balance, current_user, customer_stats,
                       days_overdue, display_status, ensure_settings, get_settings, hash_password, invoice_pdf, is_overdue, make_token,
                       next_invoice_number, recalc, require_roles, send_email, smtp_ready, verify_audit_chain, verify_password)

app = FastAPI(title="B2B Invoice & Payment Tracking", docs_url="/api/docs", openapi_url="/api/openapi.json")
WRITE = require_roles(*WRITE_ROLES)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_settings(db)
        if db.execute(select(func.count(User.id))).scalar() == 0 and config.ADMIN_PASSWORD:
            a = User(name=config.ADMIN_NAME, email=config.ADMIN_EMAIL.lower(), password_hash=hash_password(config.ADMIN_PASSWORD), role="admin")
            db.add(a)
            db.flush()
            audit(db, a, "system.bootstrap", "user", a.id, "إنشاء حساب المشرف الأول")
        db.commit()
    jobs.start_scheduler()


# ====================== العرض ======================
def u_out(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "role_label": ROLE_LABELS[u.role], "active": u.active}


def c_out(c: Customer):
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "contact_name": c.contact_name, "vatin": c.vatin, "cr_number": c.cr_number,
            "address": c.address, "credit_days": c.credit_days, "preferred_channel": c.preferred_channel, "active": c.active}


def i_out(i: Invoice, full=False):
    d = {"id": i.id, "number": i.number, "customer_id": i.customer_id, "customer": i.customer.name, "issue_date": i.issue_date.isoformat(),
         "due_date": i.due_date.isoformat(), "status": display_status(i), "base_status": i.status, "total": fm(i.total), "paid": fm(i.paid),
         "balance": fm(balance(i)), "days_overdue": days_overdue(i)}
    if full:
        d.update({"vat_rate": i.vat_rate, "subtotal": fm(i.subtotal), "vat_amount": fm(i.vat_amount), "notes": i.notes,
                  "items": [{"id": x.id, "description": x.description, "quantity": x.quantity, "unit_price": fm(x.unit_price), "line_total": fm(round(x.quantity * x.unit_price))} for x in i.items],
                  "payments": [{"id": p.id, "amount": fm(p.amount), "method": p.method, "reference": p.reference, "received_at": p.received_at.isoformat(), "source": p.source, "created_by": p.created_by, "note": p.note} for p in i.payments],
                  "customer_info": c_out(i.customer)})
    return d


def r_out(r: Reminder):
    c = r.customer
    phone = "".join(ch for ch in c.phone if ch.isdigit())
    if phone and not phone.startswith("968") and len(phone) == 8:
        phone = "968" + phone
    return {"id": r.id, "invoice_id": r.invoice_id, "invoice": r.invoice.number, "customer": c.name, "stage": r.stage, "tone": r.tone, "channel": r.channel,
            "subject": r.subject, "body": r.body, "status": r.status, "error": r.error, "mode": r.mode, "created_at": r.created_at.isoformat(),
            "sent_at": r.sent_at.isoformat() if r.sent_at else None, "email": c.email, "whatsapp_phone": phone if r.channel == "whatsapp" else None,
            "balance": fm(balance(r.invoice)), "days_overdue": days_overdue(r.invoice)}


def p_out(p: SettlementPlan):
    return {"id": p.id, "invoice_id": p.invoice_id, "invoice": p.invoice.number, "customer": p.invoice.customer.name, "status": p.status, "rationale": p.rationale,
            "installments": [{"n": x["n"], "due": x["due"], "amount": fm(x["amount"])} for x in p.installments], "balance": fm(balance(p.invoice)), "created_at": p.created_at.isoformat(), "decided_by": p.decided_by}


def t_out(t: BankTransaction, db: Session):
    sug = []
    for a in t.suggestion or []:
        inv = db.get(Invoice, a["invoice_id"])
        if inv:
            sug.append({"invoice_id": inv.id, "invoice": inv.number, "customer": inv.customer.name, "amount": fm(a["amount"]), "invoice_balance": fm(balance(inv))})
    return {"id": t.id, "date": t.txn_date.isoformat(), "amount": fm(t.amount), "description": t.description, "reference": t.reference, "counterparty": t.counterparty,
            "status": t.status, "confidence": t.confidence, "reason": t.reason, "suggestion": sug, "matched_by": t.matched_by}


# ====================== المصادقة والمستخدمون ======================
class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.email == body.email.strip().lower())).scalar_one_or_none()
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        audit(db, None, "auth.login_failed", "user", None, f"محاولة دخول فاشلة: {body.email[:80]}")
        db.commit()
        raise HTTPException(401, "البريد أو كلمة المرور غير صحيحة")
    audit(db, u, "auth.login", "user", u.id)
    db.commit()
    return {"token": make_token(u), "user": u_out(u)}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return u_out(user)


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: str


@app.get("/api/users")
def list_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return [u_out(u) for u in db.execute(select(User).order_by(User.id)).scalars()]


@app.post("/api/users")
def create_user(body: UserIn, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, "دور غير صحيح")
    if db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none():
        raise HTTPException(409, "البريد مستخدم من قبل")
    u = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.flush()
    audit(db, actor, "user.create", "user", u.id, f"{u.name} — {ROLE_LABELS[u.role]}")
    db.commit()
    return u_out(u)


@app.patch("/api/users/{uid}")
def toggle_user(uid: int, body: dict, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    if "active" in body:
        if u.id == actor.id and not body["active"]:
            raise HTTPException(400, "لا يمكنك تعطيل حسابك")
        u.active = bool(body["active"])
        audit(db, actor, "user.update", "user", u.id, f"{u.name}: {'تفعيل' if u.active else 'تعطيل'}")
    db.commit()
    return u_out(u)


@app.get("/api/settings")
def read_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_settings(db)


@app.patch("/api/settings")
def update_settings(body: dict, user: User = Depends(require_roles("admin", "finance")), db: Session = Depends(get_db)):
    ch = []
    for k, v in body.items():
        if k in DEFAULT_SETTINGS:
            db.merge(Setting(key=k, value=str(v)[:500]))
            ch.append(k)
    audit(db, user, "settings.update", "settings", None, "، ".join(ch))
    db.commit()
    return get_settings(db)


# ====================== العملاء ======================
class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = ""
    phone: str = ""
    contact_name: str = ""
    vatin: str = ""
    cr_number: str = ""
    address: str = ""
    credit_days: int = Field(default=30, ge=0, le=365)
    preferred_channel: str = "email"


@app.get("/api/customers")
def list_customers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for c in db.execute(select(Customer).order_by(Customer.name)).scalars():
        st = customer_stats(db, c.id)
        out.append({**c_out(c), "outstanding": fm(st["outstanding"]), "overdue_amount": fm(st["overdue_amount"]), "late_count": st["late_count"], "avg_days_late": st["avg_days_late"]})
    return out


@app.post("/api/customers")
def create_customer(body: CustomerIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    if db.execute(select(Customer).where(Customer.name == body.name)).scalar_one_or_none():
        raise HTTPException(409, "العميل موجود")
    if body.preferred_channel not in ("email", "whatsapp"):
        raise HTTPException(400, "قناة غير صحيحة")
    c = Customer(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, user, "customer.create", "customer", c.id, c.name)
    db.commit()
    return c_out(c)


@app.patch("/api/customers/{cid}")
def update_customer(cid: int, body: CustomerIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    c = db.get(Customer, cid)
    if not c:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, user, "customer.update", "customer", c.id, c.name)
    db.commit()
    return c_out(c)


@app.get("/api/customers/{cid}/statement")
def statement(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Customer, cid)
    if not c:
        raise HTTPException(404)
    invs = list(db.execute(select(Invoice).where(Invoice.customer_id == cid, Invoice.status != "draft").order_by(Invoice.issue_date.desc())).scalars())
    st = customer_stats(db, cid)
    return {"customer": c_out(c), "stats": {**st, "outstanding": fm(st["outstanding"]), "overdue_amount": fm(st["overdue_amount"])}, "invoices": [i_out(i) for i in invs]}


# ====================== الفواتير ======================
class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=250)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class InvoiceIn(BaseModel):
    customer_id: int
    issue_date: date | None = None
    due_date: date | None = None
    notes: str = ""
    items: list[ItemIn] = Field(min_length=1)


def _fill(db: Session, inv: Invoice, body: InvoiceIn, s: dict):
    cust = db.get(Customer, body.customer_id)
    if not cust:
        raise HTTPException(400, "العميل غير موجود")
    inv.customer_id, inv.notes = cust.id, body.notes
    inv.issue_date = body.issue_date or today_om()
    inv.due_date = body.due_date or inv.issue_date + timedelta(days=cust.credit_days or int(s["default_credit_days"]))
    if inv.due_date < inv.issue_date:
        raise HTTPException(400, "تاريخ الاستحقاق قبل الإصدار")
    inv.vat_rate = float(s["vat_rate"])
    inv.items.clear()
    for it in body.items:
        inv.items.append(InvoiceItem(description=it.description, quantity=it.quantity, unit_price=to_b(it.unit_price)))
    recalc(inv)


@app.get("/api/invoices")
def list_invoices(status: str = "", customer_id: int | None = None, q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Invoice).order_by(Invoice.id.desc())).scalars()
    out = []
    for i in rows:
        if customer_id and i.customer_id != customer_id:
            continue
        if q and q.lower() not in (i.number + " " + i.customer.name).lower():
            continue
        if status and display_status(i) != status:
            continue
        out.append(i_out(i))
    return out


@app.post("/api/invoices")
def create_invoice(body: InvoiceIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    inv = Invoice(number=next_invoice_number(db), status="draft", created_by=user.id, issue_date=today_om(), due_date=today_om())
    _fill(db, inv, body, get_settings(db))
    db.add(inv)
    db.flush()
    audit(db, user, "invoice.create", "invoice", inv.id, f"{inv.number} — {fm(inv.total):,.3f} ر.ع")
    db.commit()
    return i_out(inv, True)


@app.get("/api/invoices/{iid}")
def get_invoice(iid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(Invoice, iid)
    if not inv:
        raise HTTPException(404, "الفاتورة غير موجودة")
    out = i_out(inv, True)
    out["reminders"] = [r_out(r) for r in db.execute(select(Reminder).where(Reminder.invoice_id == iid).order_by(Reminder.id.desc())).scalars()]
    out["plans"] = [p_out(p) for p in db.execute(select(SettlementPlan).where(SettlementPlan.invoice_id == iid).order_by(SettlementPlan.id.desc())).scalars()]
    return out


@app.put("/api/invoices/{iid}")
def edit_invoice(iid: int, body: InvoiceIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    inv = db.get(Invoice, iid)
    if not inv or inv.status != "draft":
        raise HTTPException(400, "يمكن تعديل المسودات فقط")
    _fill(db, inv, body, get_settings(db))
    audit(db, user, "invoice.update", "invoice", inv.id, inv.number)
    db.commit()
    return i_out(inv, True)


@app.post("/api/invoices/{iid}/issue")
def issue_invoice(iid: int, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    inv = db.execute(select(Invoice).where(Invoice.id == iid).with_for_update()).scalar_one_or_none()
    if not inv or inv.status != "draft":
        raise HTTPException(400, "الفاتورة ليست مسودة")
    if inv.total <= 0:
        raise HTTPException(400, "إجمالي الفاتورة صفر")
    inv.status = "issued"
    audit(db, user, "invoice.issue", "invoice", inv.id, f"{inv.number} — {fm(inv.total):,.3f} ر.ع — استحقاق {inv.due_date}")
    db.commit()
    return i_out(inv, True)


@app.post("/api/invoices/{iid}/void")
def void_invoice(iid: int, body: dict, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    inv = db.execute(select(Invoice).where(Invoice.id == iid).with_for_update()).scalar_one_or_none()
    if not inv or inv.status in ("void", "paid") or inv.paid > 0:
        raise HTTPException(400, "لا يمكن إلغاء هذه الفاتورة (مسددة أو عليها دفعات)")
    reason = str(body.get("reason", "")).strip()
    if len(reason) < 3:
        raise HTTPException(400, "سبب الإلغاء مطلوب")
    inv.status = "void"
    audit(db, user, "invoice.void", "invoice", inv.id, f"{inv.number} — {reason}")
    db.commit()
    return i_out(inv, True)


@app.get("/api/invoices/{iid}/pdf")
def pdf(iid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(Invoice, iid)
    if not inv:
        raise HTTPException(404)
    return Response(invoice_pdf(inv, get_settings(db)), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{inv.number}.pdf"'})


class PaymentIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "bank_transfer"
    reference: str = ""
    received_at: date | None = None
    note: str = ""


@app.post("/api/invoices/{iid}/payments")
def add_payment(iid: int, body: PaymentIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    inv = db.execute(select(Invoice).where(Invoice.id == iid).with_for_update()).scalar_one_or_none()
    if not inv:
        raise HTTPException(404)
    if body.method not in ("bank_transfer", "cash", "cheque", "card"):
        raise HTTPException(400, "طريقة دفع غير صحيحة")
    p = apply_payment(db, inv, to_b(body.amount), body.method, body.reference.strip() or None, body.received_at or today_om(), "manual", user.name, None, body.note)
    audit(db, user, "payment.add", "invoice", inv.id, f"{inv.number}: {fm(p.amount):,.3f} ر.ع ({body.method})" + (" — سُدّدت بالكامل" if inv.status == "paid" else ""))
    db.commit()
    return i_out(inv, True)


# ====================== البنك والمطابقة ======================
@app.post("/api/bank/import")
async def bank_import(file: UploadFile = File(...), user: User = Depends(WRITE), db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8-sig")
    res = import_bank_csv(db, text, user.name)
    audit(db, user, "bank.import", "bank", None, f"{file.filename}: {res}")
    db.commit()
    return res


@app.get("/api/bank/transactions")
def bank_list(status: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(BankTransaction).order_by(BankTransaction.id.desc()).limit(300)
    return [t_out(t, db) for t in db.execute(q).scalars() if not status or t.status == status]


@app.post("/api/bank/reconcile")
def bank_reconcile(user: User = Depends(WRITE), db: Session = Depends(get_db)):
    res = jobs.job_reconcile(db)
    audit(db, user, "agent.reconcile", "bank", None, res, actor="وكيل المطابقة")
    db.commit()
    return {"detail": res}


class ConfirmIn(BaseModel):
    allocations: list[dict] | None = None  # [{invoice_id, amount}] — إن لم تُرسل تُعتمد المقترحة


@app.post("/api/bank/transactions/{tid}/confirm")
def bank_confirm(tid: int, body: ConfirmIn, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    t = db.get(BankTransaction, tid)
    if not t or t.status not in ("unmatched", "suggested"):
        raise HTTPException(400, "الحركة غير قابلة للمطابقة")
    alloc = body.allocations or t.suggestion
    if not alloc:
        raise HTTPException(400, "لا يوجد توزيع لتأكيده")
    if body.allocations:  # المبالغ المرسلة بالريال العماني
        alloc = [{"invoice_id": int(a["invoice_id"]), "amount": to_b(a["amount"])} for a in body.allocations]
    try:
        apply_allocations(db, t, alloc, user.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, user, "bank.confirm", "bank_txn", t.id, f"{fm(t.amount):,.3f} ر.ع — طابقها {user.name}")
    db.commit()
    return t_out(t, db)


@app.post("/api/bank/transactions/{tid}/ignore")
def bank_ignore(tid: int, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    t = db.get(BankTransaction, tid)
    if not t or t.status == "matched":
        raise HTTPException(400, "لا يمكن تجاهل هذه الحركة")
    t.status = "ignored"
    audit(db, user, "bank.ignore", "bank_txn", t.id, f"{fm(t.amount):,.3f} ر.ع")
    db.commit()
    return t_out(t, db)


# ====================== التحصيل ======================
@app.post("/api/collections/run")
def collections_run(user: User = Depends(WRITE), db: Session = Depends(get_db)):
    res = run_dunning(db)
    db.commit()
    return res


@app.get("/api/reminders")
def list_reminders(status: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Reminder).order_by(Reminder.id.desc()).limit(200)).scalars()
    return [r_out(r) for r in rows if not status or r.status == status]


class ReminderEdit(BaseModel):
    subject: str | None = None
    body: str | None = None


@app.patch("/api/reminders/{rid}")
def edit_reminder(rid: int, body: ReminderEdit, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    r = db.get(Reminder, rid)
    if not r or r.status not in ("draft", "approved", "failed"):
        raise HTTPException(400, "لا يمكن تعديل هذا التذكير")
    if body.subject is not None:
        r.subject = body.subject[:200]
    if body.body is not None:
        r.body = body.body
    audit(db, user, "reminder.edit", "reminder", r.id, r.invoice.number)
    db.commit()
    return r_out(r)


@app.post("/api/reminders/{rid}/{action}")
def reminder_action(rid: int, action: str, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    r = db.get(Reminder, rid)
    if not r:
        raise HTTPException(404)
    if action == "skip":
        r.status = "skipped"
    elif action == "approve":
        r.status = "approved"
    elif action == "mark_sent":  # أُرسلت يدوياً (واتساب مثلاً)
        r.status, r.sent_at = "sent", now_om()
    elif action == "send":
        try:
            jobs.deliver(db, r)
        except Exception as e:  # noqa: BLE001
            r.status, r.error = "failed", str(e)[:250]
            audit(db, user, "reminder.failed", "reminder", r.id, f"{r.invoice.number}: {r.error}")
            db.commit()
            raise HTTPException(400, f"تعذّر الإرسال: {r.error}")
    else:
        raise HTTPException(404)
    audit(db, user, f"reminder.{action}", "reminder", r.id, f"{r.invoice.number} — {r.customer.name} ({r.stage})")
    db.commit()
    return r_out(r)


@app.get("/api/plans")
def list_plans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [p_out(p) for p in db.execute(select(SettlementPlan).order_by(SettlementPlan.id.desc()).limit(100)).scalars()]


@app.post("/api/plans/{pid}/{action}")
def plan_action(pid: int, action: str, user: User = Depends(WRITE), db: Session = Depends(get_db)):
    p = db.get(SettlementPlan, pid)
    if not p or p.status != "proposed" or action not in ("accept", "reject"):
        raise HTTPException(400, "لا يمكن تنفيذ الإجراء")
    p.status = "active" if action == "accept" else "rejected"
    p.decided_by = user.name
    if action == "accept":
        p.paid_at_start = p.invoice.paid
    audit(db, user, f"plan.{action}", "invoice", p.invoice_id, f"{p.invoice.number} — {len(p.installments)} دفعات")
    db.commit()
    return p_out(p)


# ====================== بوابة الدفع (Webhook موقّع) ======================
@app.post("/api/webhooks/payments")
async def payment_webhook(request: Request, x_signature: str = Header(default=""), db: Session = Depends(get_db)):
    """يستقبل إشعار دفع من بوابة الدفع: {invoice_number, amount (ر.ع), reference} بتوقيع HMAC-SHA256 على الجسم."""
    raw = await request.body()
    if not config.WEBHOOK_SECRET:
        raise HTTPException(503, "لم يُضبط WEBHOOK_SECRET")
    if not hmac.compare_digest(hmac.new(config.WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest(), x_signature):
        raise HTTPException(401, "توقيع غير صحيح")
    data = await request.json()
    inv = db.execute(select(Invoice).where(Invoice.number == data.get("invoice_number")).with_for_update()).scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "فاتورة غير معروفة")
    ref = str(data.get("reference", "")).strip()
    if not ref:
        raise HTTPException(400, "المرجع مطلوب لمنع التكرار")
    if db.execute(select(Payment.id).where(Payment.source == "webhook", Payment.reference == ref)).first():
        return {"recorded": False, "duplicate": True}
    p = apply_payment(db, inv, to_b(data["amount"]), "card", ref, today_om(), "webhook", "بوابة الدفع")
    audit(db, None, "payment.webhook", "invoice", inv.id, f"{inv.number}: {fm(p.amount):,.3f} ر.ع — {ref}", actor="بوابة الدفع")
    db.commit()
    return {"recorded": True, "status": inv.status}


# ====================== لوحة التحكم والتقارير ======================
@app.get("/api/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = today_om()
    invs = list(db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial", "paid"]))).scalars())
    open_ = [i for i in invs if i.status in ("issued", "partial")]
    over = [i for i in open_ if i.due_date < today]
    month_start = today.replace(day=1)
    collected = sum(p.amount for i in invs for p in i.payments if p.received_at >= month_start)
    trend = {}
    for k in range(5, -1, -1):
        y, m = today.year, today.month - k
        while m <= 0:
            y, m = y - 1, m + 12
        trend[f"{y}-{m:02d}"] = {"month": f"{y}-{m:02d}", "issued": 0, "collected": 0}
    for i in invs:
        k = i.issue_date.strftime("%Y-%m")
        if k in trend:
            trend[k]["issued"] += i.total
        for p in i.payments:
            k = p.received_at.strftime("%Y-%m")
            if k in trend:
                trend[k]["collected"] += p.amount
    paid = [i for i in invs if i.status == "paid" and i.payments]
    dso = round(sum((max(p.received_at for p in i.payments) - i.issue_date).days for i in paid) / len(paid), 1) if paid else None
    top = sorted(((c, sum(balance(i) for i in over if i.customer_id == c.id)) for c in {i.customer for i in over}), key=lambda x: -x[1])[:5]
    return {"outstanding": fm(sum(balance(i) for i in open_)), "overdue": fm(sum(balance(i) for i in over)), "overdue_count": len(over), "open_count": len(open_),
            "collected_month": fm(collected), "dso": dso, "aging": aging(db),
            "trend": [{"month": v["month"], "issued": fm(v["issued"]), "collected": fm(v["collected"])} for v in trend.values()],
            "top_overdue": [{"id": c.id, "name": c.name, "amount": fm(a)} for c, a in top],
            "pending_reminders": db.execute(select(func.count(Reminder.id)).where(Reminder.status.in_(["draft", "approved"]))).scalar(),
            "pending_plans": db.execute(select(func.count(SettlementPlan.id)).where(SettlementPlan.status == "proposed")).scalar(),
            "bank_to_review": db.execute(select(func.count(BankTransaction.id)).where(BankTransaction.status.in_(["suggested", "unmatched"]))).scalar(),
            "smtp": smtp_ready(), "ai_enabled": ai_enabled()}


# ====================== المهام والوكلاء والتدقيق ======================
@app.get("/api/jobs")
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    nxt = jobs.next_runs()
    out = []
    for name, (title, _, when) in jobs.JOBS.items():
        last = db.execute(select(JobRun).where(JobRun.name == name).order_by(JobRun.id.desc()).limit(1)).scalar_one_or_none()
        out.append({"name": name, "title": title, "schedule": when, "next_run": nxt.get(name),
                    "last": {"status": last.status, "detail": last.detail, "started": last.started.isoformat(), "trigger": last.trigger} if last else None})
    return out


@app.post("/api/jobs/{name}/run")
def run_job_now(name: str, user: User = Depends(WRITE)):
    if name not in jobs.JOBS:
        raise HTTPException(404)
    return jobs.run_job(name, "manual", user)


class ChatIn(BaseModel):
    agent: str
    message: str = Field(min_length=1, max_length=1000)
    history: list[dict] = []


@app.post("/api/agents/chat")
def agents_chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .agent_chat import chat, AGENTS
    if body.agent not in AGENTS:
        raise HTTPException(404, "وكيل غير معروف")
    out = chat(db, user, body.agent, body.message, body.history)
    audit(db, user, "agent.chat", "agent", None, f"{AGENTS[body.agent]['name']}: {body.message[:120]}", actor=user.name)
    db.commit()
    return out


@app.get("/api/agents/catalog")
def agents_catalog(user: User = Depends(current_user)):
    from .agent_chat import AGENTS
    return [{"key": k, "name": v["name"], "chips": v["chips"], "tools": v["tools"]} for k, v in AGENTS.items()]


@app.get("/api/agents/overview")
def agents_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cnt = lambda model, col, vals: db.execute(select(func.count(model.id)).where(col.in_(vals))).scalar()  # noqa: E731
    acts = [{"id": a.id, "ts": a.ts.isoformat(), "agent": a.user_name, "details": a.details}
            for a in db.execute(select(AuditLog).where(AuditLog.action.like("agent.%") & (AuditLog.action != "agent.chat")).order_by(AuditLog.id.desc()).limit(25)).scalars()]
    return {"ai_enabled": ai_enabled(), "model": config.AI_MODEL if ai_enabled() else None, "smtp": smtp_ready(),
            "reminders": {s: cnt(Reminder, Reminder.status, [s]) for s in ("draft", "approved", "sent", "failed", "skipped")},
            "plans": {s: cnt(SettlementPlan, SettlementPlan.status, [s]) for s in ("proposed", "active", "completed", "defaulted", "rejected")},
            "bank": {s: cnt(BankTransaction, BankTransaction.status, [s]) for s in ("matched", "suggested", "unmatched", "ignored")},
            "activity": acts}


@app.get("/api/audit/logs")
def audit_logs(limit: int = 200, user: User = Depends(require_roles("admin", "finance")), db: Session = Depends(get_db)):
    return [{"id": a.id, "ts": a.ts.isoformat(), "user": a.user_name, "action": a.action, "details": a.details}
            for a in db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))).scalars()]


@app.get("/api/audit/verify")
def audit_verify(user: User = Depends(require_roles("admin", "finance")), db: Session = Depends(get_db)):
    return verify_audit_chain(db)


@app.get("/api/system")
def system(user: User = Depends(current_user)):
    return {"ai_enabled": ai_enabled(), "smtp": smtp_ready(), "webhook": bool(config.WEBHOOK_SECRET), "time": now_om().isoformat()}


# ====================== الواجهة ======================
DIST = config.BASE_DIR.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
