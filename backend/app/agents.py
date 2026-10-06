"""وكيلا التحصيل والمطابقة.

* وكيل التحصيل والتذكير: يولّد تذكيرات تتكيّف مع سجل كل عميل (ودّية/محايدة/حازمة) قبل الاستحقاق وبعده، ويقترح خطط تسوية للمتأخرات، ويراقب التزام العميل بالخطة.
* وكيل المطابقة البنكية: يطابق التحويلات الواردة مع الفواتير المفتوحة ويُغلق المسددة آلياً عند الثقة العالية، وإلا يقترح للمراجعة البشرية.

المنطق الأساسي قواعد صارمة تعمل دائماً. عند ضبط ANTHROPIC_API_KEY يعيد Claude صياغة نص التذكير فقط (الأرقام والتواريخ ثابتة).
"""
import csv
import hashlib
import io
import itertools
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import BankTransaction, Customer, Invoice, Reminder, SettlementPlan, fm, now_om, to_b, today_om
from .services import (apply_payment, audit, balance, customer_stats, days_overdue, get_settings, is_overdue)


def ai_enabled() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def _rewrite(body: str, tone: str) -> str | None:
    if not ai_enabled():
        return None
    try:
        import anthropic
        r = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(
            model=config.AI_MODEL, max_tokens=700,
            messages=[{"role": "user", "content": f"أعد صياغة رسالة التحصيل التالية بعربية تجارية عُمانية مهذبة بنبرة ({tone}) دون تغيير أي رقم أو تاريخ أو اسم أو التزام، وأعد النص فقط:\n\n{body}"}])
        out = "".join(b.text for b in r.content if b.type == "text").strip()
        return out or None
    except Exception:  # noqa: BLE001
        return None


# ====================== وكيل التحصيل ======================
TITLES = {"pre": "تذكير ودّي بموعد الاستحقاق", "due": "الفاتورة تستحق اليوم", "late": "تذكير بفاتورة متأخرة", "final": "إشعار نهائي بفاتورة متأخرة"}


def _offsets(s: dict) -> list[int]:
    return sorted({int(x) for x in s["dunning_offsets"].split(",") if x.strip().lstrip("-+").isdigit()})


def _tone(st: dict, offset: int) -> str:
    if offset <= 0:
        return "neutral" if st["late_count"] >= 3 else "friendly"
    if offset >= 30 or st["late_count"] >= 3 or st["avg_days_late"] >= 15 or st["open_overdue"] >= 2:
        return "firm"
    return "neutral"


def _stage_kind(offset: int) -> str:
    return "pre" if offset < 0 else "due" if offset == 0 else "final" if offset >= 30 else "late"


def build_message(inv: Invoice, st: dict, s: dict, offset: int, tone: str) -> tuple[str, str]:
    c = inv.customer
    kind = _stage_kind(offset)
    who = c.contact_name or c.name
    due, bal, od = inv.due_date.isoformat(), f"{fm(balance(inv)):,.3f}", days_overdue(inv)
    bank = f"\nبيانات السداد:\n{s['bank_details']}" if s["bank_details"] else ""
    paid_line = f" وقد استلمنا منكم {fm(inv.paid):,.3f} ر.ع مع الشكر، ويتبقى {bal} ر.ع." if inv.paid else ""
    head = f"السادة / {who} المحترمين،\nتحية طيبة وبعد،\n"
    tail = f"{bank}\n\nوفي حال تم السداد، نرجو التكرم بتجاهل هذه الرسالة وإفادتنا بإشعار التحويل.\nمع خالص التقدير،\n{s['company_name']}"
    if kind == "pre":
        subject = f"تذكير ودّي: الفاتورة {inv.number} تستحق في {due}"
        body = head + f"نود تذكيركم بأن الفاتورة رقم {inv.number} بمبلغ {bal} ر.ع تستحق السداد بتاريخ {due}، أي بعد {abs(offset)} أيام.{paid_line}\nشاكرين لكم حسن تعاونكم." + tail
    elif kind == "due":
        subject = f"الفاتورة {inv.number} تستحق اليوم"
        body = head + f"نفيدكم بأن الفاتورة رقم {inv.number} بمبلغ {bal} ر.ع تستحق السداد اليوم {due}.{paid_line}\nنأمل إتمام السداد في أقرب وقت." + tail
    elif kind == "late":
        subject = f"تذكير: الفاتورة {inv.number} متأخرة {od} يوماً"
        body = head + f"نفيدكم بأن الفاتورة رقم {inv.number} تجاوزت تاريخ استحقاقها ({due}) بمدة {od} يوماً، والمتبقي {bal} ر.ع.{paid_line}"
        if tone == "firm":
            body += f"\nونلفت عنايتكم إلى وجود {st['open_overdue']} فاتورة متأخرة بإجمالي {fm(st['overdue_amount']):,.3f} ر.ع، ونأمل السداد خلال 7 أيام حفاظاً على شروط الائتمان الممنوحة لكم."
        else:
            body += "\nنأمل التكرم بإتمام السداد خلال الأيام القادمة."
        body += tail
    else:
        subject = f"إشعار نهائي: الفاتورة {inv.number} متأخرة {od} يوماً"
        body = head + f"رغم تذكيراتنا السابقة، ما زالت الفاتورة رقم {inv.number} غير مسددة بعد تجاوزها تاريخ الاستحقاق ({due}) بمدة {od} يوماً، والمتبقي {bal} ر.ع.{paid_line}\nنأمل السداد خلال 7 أيام، ويسعدنا إن كانت لديكم ظروف أن نبحث معكم خطة سداد على دفعات، وإلا اضطررنا لمراجعة شروط الائتمان وإحالة الحساب للإجراءات المناسبة." + tail
    return subject, body


def _channel(c: Customer) -> str:
    if c.preferred_channel == "whatsapp" and c.phone:
        return "whatsapp"
    if c.email:
        return "email"
    return "whatsapp" if c.phone else "none"


def generate_reminder(db: Session, inv: Invoice, s: dict, today: date) -> Reminder | None:
    if inv.status not in ("issued", "partial"):
        return None
    if db.execute(select(SettlementPlan.id).where(SettlementPlan.invoice_id == inv.id, SettlementPlan.status == "active")).first():
        return None
    diff = (today - inv.due_date).days
    applicable = [o for o in _offsets(s) if o <= diff]
    if not applicable:
        return None
    offset = max(applicable)
    stage = f"d{offset:+d}"
    if db.execute(select(Reminder.id).where(Reminder.invoice_id == inv.id, Reminder.stage == stage)).first():
        return None
    channel = _channel(inv.customer)
    if channel == "none":
        return None
    st = customer_stats(db, inv.customer_id)
    tone = _tone(st, offset)
    subject, body = build_message(inv, st, s, offset, tone)
    mode = "rules"
    better = _rewrite(body, {"friendly": "ودّية", "neutral": "محايدة", "firm": "حازمة ومهذبة"}[tone])
    if better:
        body, mode = better, "ai"
    status = "approved" if (offset <= 0 and tone == "friendly" and s["auto_send"] == "1" and channel == "email") else "draft"
    r = Reminder(invoice_id=inv.id, customer_id=inv.customer_id, stage=stage, tone=tone, channel=channel, subject=subject, body=body, status=status, mode=mode)
    db.add(r)
    db.flush()
    return r


def propose_plan(db: Session, inv: Invoice, today: date) -> SettlementPlan | None:
    bal = balance(inv)
    if inv.status not in ("issued", "partial") or days_overdue(inv, today) < 14 or bal < to_b(100):
        return None
    if db.execute(select(SettlementPlan.id).where(SettlementPlan.invoice_id == inv.id, SettlementPlan.status.in_(["proposed", "active"]))).first():
        return None
    st = customer_stats(db, inv.customer_id)
    n = 2 if bal <= to_b(500) else 3 if bal <= to_b(5000) else 4
    if st["late_count"] >= 3 and n > 2:
        n -= 1  # عميل متكرر التأخر: عدد أقل وأسرع من الدفعات
    first = round(bal * 0.4)
    rest = bal - first
    each = rest // (n - 1)
    inst = [{"n": 1, "due": (today + timedelta(days=7)).isoformat(), "amount": first}]
    for k in range(2, n + 1):
        inst.append({"n": k, "due": (today + timedelta(days=7 + 30 * (k - 1))).isoformat(), "amount": each if k < n else rest - each * (n - 2)})
    why = (f"الفاتورة متأخرة {days_overdue(inv, today)} يوماً والمتبقي {fm(bal):,.3f} ر.ع. "
           f"سجل العميل: {st['late_count']} فاتورة متأخرة سابقاً بمتوسط {st['avg_days_late']} يوماً. "
           f"قُسّم المتبقي إلى {n} دفعات، الأولى 40% خلال 7 أيام لتأمين جزء كبير سريعاً، والباقي شهرياً.")
    p = SettlementPlan(invoice_id=inv.id, installments=inst, rationale=why, paid_at_start=inv.paid)
    db.add(p)
    db.flush()
    return p


def monitor_plans(db: Session, today: date) -> dict:
    done = broken = 0
    for p in db.execute(select(SettlementPlan).where(SettlementPlan.status == "active")).scalars():
        inv = p.invoice
        if inv.status == "paid":
            p.status, done = "completed", done + 1
            continue
        paid_since = inv.paid - p.paid_at_start
        due_cum = sum(i["amount"] for i in p.installments if date.fromisoformat(i["due"]) < today)
        if paid_since < due_cum:
            p.status, broken = "defaulted", broken + 1
    return {"completed": done, "defaulted": broken}


def run_dunning(db: Session, today: date | None = None) -> dict:
    today = today or today_om()
    s = get_settings(db)
    created = plans = 0
    for inv in db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial"]))).scalars():
        if generate_reminder(db, inv, s, today):
            created += 1
        if propose_plan(db, inv, today):
            plans += 1
    mon = monitor_plans(db, today)
    audit(db, None, "agent.dunning", "system", None, f"أنشأ {created} تذكير و{plans} خطة تسوية مقترحة؛ خطط مكتملة {mon['completed']}، متعثرة {mon['defaulted']}", actor="وكيل التحصيل")
    return {"reminders": created, "plans_proposed": plans, **mon}


# ====================== وكيل المطابقة البنكية ======================
INV_RE = re.compile(r"INV[-\s_]?(\d{4})[-\s_]?(\d{4})", re.I)
_AR_CLEAN = re.compile(r"[ً-ْـ]")


def _norm(t: str) -> str:
    t = _AR_CLEAN.sub("", t or "").lower()
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^\w\s]", " ", t)


_STOP = {"شركه", "مؤسسه", "للتجاره", "ش", "م", "م.م", "co", "llc", "ltd", "the", "and", "و"}


def _name_score(text: str, name: str) -> float:
    a, b = _norm(text), _norm(name)
    if not a.strip() or not b.strip():
        return 0.0
    ta = {w for w in a.split() if w not in _STOP}
    tb = {w for w in b.split() if w not in _STOP}
    contain = len(ta & tb) / len(tb) if tb else 0
    return max(SequenceMatcher(None, a.strip(), b.strip()).ratio(), contain if len(ta & tb) >= 1 and contain >= 0.6 else 0)


def _fifo(invs: list[Invoice], amount: int) -> list[dict]:
    out, left = [], amount
    for i in sorted(invs, key=lambda x: x.due_date):
        if left <= 0:
            break
        take = min(left, balance(i))
        out.append({"invoice_id": i.id, "amount": take})
        left -= take
    return out


def match_txn(db: Session, txn: BankTransaction, open_invoices: list[Invoice]) -> tuple[float, str, list[dict]]:
    text = f"{txn.reference} {txn.description} {txn.counterparty}"
    by_no = {i.number.replace("-", ""): i for i in open_invoices}
    for m in INV_RE.finditer(text):
        inv = by_no.get(f"INV{m.group(1)}{m.group(2)}")
        if inv:
            b = balance(inv)
            if txn.amount == b:
                return 0.98, f"رقم الفاتورة {inv.number} مذكور والمبلغ يطابق المتبقي تماماً", [{"invoice_id": inv.id, "amount": b}]
            if txn.amount < b:
                return 0.92, f"رقم الفاتورة {inv.number} مذكور؛ دفعة جزئية ({fm(txn.amount):,.3f} من {fm(b):,.3f})", [{"invoice_id": inv.id, "amount": txn.amount}]
            return 0.55, f"رقم الفاتورة {inv.number} مذكور لكن المبلغ أكبر من المتبقي ({fm(b):,.3f}) — يحتاج مراجعة", [{"invoice_id": inv.id, "amount": b}]
    best, best_c = 0.0, None
    cust_ids = {i.customer_id for i in open_invoices}
    for cid in cust_ids:
        c = next(i.customer for i in open_invoices if i.customer_id == cid)
        sc = max(_name_score(txn.counterparty, c.name), _name_score(txn.description, c.name))
        if sc > best:
            best, best_c = sc, c
    if best_c and best >= 0.72:
        mine = [i for i in open_invoices if i.customer_id == best_c.id]
        exact = [i for i in mine if balance(i) == txn.amount]
        if len(exact) == 1:
            return 0.88, f"اسم العميل «{best_c.name}» يتطابق والمبلغ يساوي متبقي فاتورة واحدة ({exact[0].number})", [{"invoice_id": exact[0].id, "amount": txn.amount}]
        if len(exact) > 1:
            old = sorted(exact, key=lambda x: x.due_date)[0]
            return 0.7, f"العميل «{best_c.name}» لديه {len(exact)} فواتير بنفس المبلغ؛ اقتُرحت الأقدم", [{"invoice_id": old.id, "amount": txn.amount}]
        for size in range(2, min(4, len(mine)) + 1):
            for combo in itertools.combinations(sorted(mine, key=lambda x: x.due_date), size):
                if sum(balance(i) for i in combo) == txn.amount:
                    return 0.8, f"المبلغ يساوي مجموع متبقي {size} فواتير للعميل «{best_c.name}»", [{"invoice_id": i.id, "amount": balance(i)} for i in combo]
        total = sum(balance(i) for i in mine)
        if txn.amount < total:
            return 0.6, f"العميل «{best_c.name}» مطابق لكن المبلغ لا يطابق فاتورة بعينها؛ توزيع مقترح على الأقدم أولاً", _fifo(mine, txn.amount)
        return 0.4, f"المبلغ أكبر من إجمالي مستحقات «{best_c.name}»", _fifo(mine, total)
    same = [i for i in open_invoices if balance(i) == txn.amount]
    if len(same) == 1:
        return 0.65, f"لا يوجد اسم عميل مطابق، لكن مبلغ التحويل يساوي متبقي الفاتورة {same[0].number} فقط", [{"invoice_id": same[0].id, "amount": txn.amount}]
    return 0.0, "لا توجد فاتورة مطابقة", []


def reconcile_txn(db: Session, txn: BankTransaction, actor: str = "وكيل المطابقة") -> str:
    s = get_settings(db)
    open_inv = list(db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial"]))).scalars())
    conf, reason, alloc = match_txn(db, txn, open_inv)
    txn.confidence, txn.reason, txn.suggestion = conf, reason, alloc or None
    if alloc and conf >= float(s["auto_threshold"]) and s["auto_reconcile"] == "1":
        apply_allocations(db, txn, alloc, "وكيل المطابقة (تلقائي)")
        audit(db, None, "agent.reconcile", "bank_txn", txn.id, f"طابق {fm(txn.amount):,.3f} ر.ع تلقائياً (ثقة {conf:.0%}): {reason}", actor=actor)
        return "matched"
    txn.status = "suggested" if alloc else "unmatched"
    return txn.status


def apply_allocations(db: Session, txn: BankTransaction, alloc: list[dict], by: str):
    total = sum(a["amount"] for a in alloc)
    if total != txn.amount and total > txn.amount:
        raise ValueError("التوزيع أكبر من مبلغ التحويل")
    for a in alloc:
        inv = db.execute(select(Invoice).where(Invoice.id == a["invoice_id"]).with_for_update()).scalar_one()
        apply_payment(db, inv, a["amount"], "bank_transfer", f"BANK-{txn.id}-{inv.number}", txn.txn_date, "bank_import", by, txn.id, txn.description[:200])
    txn.status, txn.matched_by = "matched", by


def _parse_date(v: str) -> date:
    v = v.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError("تاريخ غير صالح")


def import_bank_csv(db: Session, text: str, user_name: str) -> dict:
    """أعمدة CSV: date, amount, description, reference, counterparty — تُستورد الإيداعات فقط."""
    new = dup = bad = debit = 0
    created: list[BankTransaction] = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            amt = to_b(float(str(row["amount"]).replace(",", "").strip()))
            if amt <= 0:
                debit += 1
                continue
            d = _parse_date(row["date"])
            desc, ref, cp = (row.get("description") or "").strip(), (row.get("reference") or "").strip(), (row.get("counterparty") or "").strip()
            fp = hashlib.sha256(f"{d}|{amt}|{desc}|{ref}|{cp}".encode()).hexdigest()
            if db.execute(select(BankTransaction.id).where(BankTransaction.fingerprint == fp)).first():
                dup += 1
                continue
            t = BankTransaction(fingerprint=fp, txn_date=d, amount=amt, description=desc, reference=ref, counterparty=cp)
            db.add(t)
            db.flush()
            created.append(t)
            new += 1
        except Exception:  # noqa: BLE001
            bad += 1
    res = {"matched": 0, "suggested": 0, "unmatched": 0}
    for t in created:
        res[reconcile_txn(db, t)] += 1
    audit(db, None, "agent.reconcile", "bank_txn", None, f"استورد {user_name} {new} حركة؛ مطابقة تلقائية {res['matched']}، مقترحة {res['suggested']}، بلا مطابقة {res['unmatched']}", actor="وكيل المطابقة")
    return {"imported": new, "duplicates": dup, "rejected": bad, "debits_skipped": debit, **res}
