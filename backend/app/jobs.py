"""المهام المجدولة بتوقيت مسقط:
* dunning        — يومياً 08:00: وكيل التحصيل يولّد التذكيرات وخطط التسوية ويراقب الخطط.
* send_approved  — كل 10 دقائق: يرسل التذكيرات المعتمدة بالبريد (عند ضبط SMTP).
* reconcile      — كل ساعة: يعيد مطابقة الحركات البنكية غير المطابقة مع الفواتير الجديدة.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from . import config
from .agents import reconcile_txn, run_dunning
from .db import SessionLocal
from .models import BankTransaction, JobRun, Reminder, now_om, OM_TZ
from .services import audit, get_settings, invoice_pdf, send_email, smtp_ready


def deliver(db, r: Reminder) -> None:
    """يرسل تذكير بريد واحد مع الفاتورة PDF مرفقة؛ يرفع استثناء عند الفشل."""
    s = get_settings(db)
    if r.channel != "email":
        raise ValueError("القناة ليست بريداً")
    if not r.customer.email:
        raise ValueError("لا يوجد بريد للعميل")
    if not smtp_ready():
        raise RuntimeError("لم يُضبط SMTP في ملف .env")
    send_email(r.customer.email, r.subject, r.body, (f"{r.invoice.number}.pdf", invoice_pdf(r.invoice, s)))
    r.status, r.sent_at, r.error = "sent", now_om(), ""


def job_dunning(db) -> str:
    r = run_dunning(db)
    return f"تذكيرات جديدة {r['reminders']}، خطط مقترحة {r['plans_proposed']}، خطط مكتملة {r['completed']}، متعثرة {r['defaulted']}"


def job_send_approved(db) -> str:
    rows = list(db.execute(select(Reminder).where(Reminder.status == "approved", Reminder.channel == "email")).scalars())
    if not rows:
        return "لا توجد تذكيرات معتمدة"
    if not smtp_ready():
        return f"{len(rows)} تذكير معتمد بانتظار ضبط SMTP"
    ok = bad = 0
    for r in rows:
        try:
            deliver(db, r)
            ok += 1
        except Exception as e:  # noqa: BLE001
            r.status, r.error = "failed", str(e)[:250]
            bad += 1
    return f"أُرسل {ok}، فشل {bad}"


def job_reconcile(db) -> str:
    rows = list(db.execute(select(BankTransaction).where(BankTransaction.status.in_(["unmatched", "suggested"]))).scalars())
    res = {"matched": 0, "suggested": 0, "unmatched": 0}
    for t in rows:
        res[reconcile_txn(db, t)] += 1
    return f"أُعيدت مطابقة {len(rows)} حركة: مطابقة {res['matched']}، مقترحة {res['suggested']}"


JOBS = {
    "dunning": ("وكيل التحصيل: التذكيرات وخطط التسوية", job_dunning, "يومياً 08:00"),
    "send_approved": ("إرسال التذكيرات المعتمدة", job_send_approved, "كل 10 دقائق"),
    "reconcile": ("إعادة مطابقة الحركات البنكية", job_reconcile, "كل ساعة"),
}


def run_job(name: str, trigger: str = "schedule", user=None) -> dict:
    title, fn, _ = JOBS[name]
    with SessionLocal() as db:
        run = JobRun(name=name, trigger=trigger)
        db.add(run)
        db.commit()
        try:
            run.detail, run.status = fn(db), "success"
        except Exception as e:  # noqa: BLE001
            db.rollback()
            run = db.get(JobRun, run.id)
            run.status, run.detail = "failed", f"{type(e).__name__}: {e}"[:500]
        run.finished = now_om()
        if trigger == "manual" or run.status == "failed":
            audit(db, user, "job.run", "job", run.id, f"{title} — {run.status} — {run.detail}", actor="" if user else "المجدول")
        db.commit()
        return {"name": name, "status": run.status, "detail": run.detail}


_scheduler = None


def start_scheduler():
    global _scheduler
    if config.DISABLE_SCHEDULER or _scheduler:
        return
    s = BackgroundScheduler(timezone=OM_TZ)
    s.add_job(run_job, CronTrigger(hour=8, minute=0), args=["dunning"], id="dunning")
    s.add_job(run_job, IntervalTrigger(minutes=10), args=["send_approved"], id="send_approved")
    s.add_job(run_job, IntervalTrigger(hours=1), args=["reconcile"], id="reconcile")
    s.start()
    _scheduler = s


def next_runs() -> dict:
    return {j.id: j.next_run_time.isoformat() if j.next_run_time else None for j in _scheduler.get_jobs()} if _scheduler else {}
