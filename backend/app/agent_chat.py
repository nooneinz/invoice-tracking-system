"""محادثة الوكلاء: تسأل بالعربية فيستدعي الوكيل أدوات النظام (للقراءة فقط) ويجيب.
مع ANTHROPIC_API_KEY يقرر Claude الأدوات في حلقة tool use؛ وبدونه يفهم موجّه محلي الأسئلة الشائعة.
لا تغيّر الأدوات أي بيانات؛ إرسال التذكيرات واعتماد الخطط وتأكيد المطابقة تبقى بيد المستخدم."""
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .agents import ai_enabled
from .models import BankTransaction, Customer, Invoice, Reminder, SettlementPlan, fm, today_om
from .services import aging, balance, customer_stats, days_overdue, display_status, is_overdue


def _omr(n) -> str:
    return f"{float(n):,.3f} ر.ع"


def t_overdue_invoices(db, user, a):
    rows = [i for i in db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial"]))).scalars() if is_overdue(i)]
    rows.sort(key=lambda i: -days_overdue(i))
    return [{"الفاتورة": i.number, "العميل": i.customer.name, "المتبقي": fm(balance(i)), "أيام_التأخير": days_overdue(i), "الاستحقاق": i.due_date.isoformat()} for i in rows[:20]]


def t_aging_report(db, user, a):
    return aging(db)


def t_customer_statement(db, user, a):
    name = (a.get("name") or "").strip()
    c = next((x for x in db.execute(select(Customer)).scalars() if name and name in x.name), None)
    if not c:
        return {"خطأ": "لم أجد عميلاً بهذا الاسم"}
    st = customer_stats(db, c.id)
    invs = db.execute(select(Invoice).where(Invoice.customer_id == c.id, Invoice.status.in_(["issued", "partial"])).order_by(Invoice.due_date)).scalars()
    return {"العميل": c.name, "فواتير_مفتوحة": [{"الفاتورة": i.number, "المتبقي": fm(balance(i)), "الحالة": display_status(i), "الاستحقاق": i.due_date.isoformat()} for i in invs],
            "المستحق_الكلي": fm(st["outstanding"]), "المتأخر": fm(st["overdue_amount"]), "فواتير_سددها_متأخراً": st["late_count"], "متوسط_التأخر_يوم": st["avg_days_late"]}


def t_invoice_details(db, user, a):
    num = (a.get("number") or "").strip().upper()
    i = db.execute(select(Invoice).where(Invoice.number == num)).scalar_one_or_none()
    if not i:
        return {"خطأ": "لم أجد فاتورة بهذا الرقم"}
    return {"الفاتورة": i.number, "العميل": i.customer.name, "الحالة": display_status(i), "الإجمالي": fm(i.total), "المدفوع": fm(i.paid), "المتبقي": fm(balance(i)),
            "الاستحقاق": i.due_date.isoformat(), "أيام_التأخير": days_overdue(i), "الدفعات": [{"المبلغ": fm(p.amount), "التاريخ": p.received_at.isoformat(), "المصدر": p.source} for p in i.payments]}


def t_collection_priorities(db, user, a):
    scores = {}
    for i in db.execute(select(Invoice).where(Invoice.status.in_(["issued", "partial"]))).scalars():
        if is_overdue(i):
            d = scores.setdefault(i.customer_id, {"c": i.customer, "amt": 0, "maxd": 0})
            d["amt"] += balance(i)
            d["maxd"] = max(d["maxd"], days_overdue(i))
    out = []
    for cid, d in scores.items():
        st = customer_stats(db, cid)
        out.append({"العميل": d["c"].name, "المتأخر": fm(d["amt"]), "أقدم_تأخير_يوم": d["maxd"], "سوابق_تأخر": st["late_count"],
                    "الأولوية": round(fm(d["amt"]) * (1 + d["maxd"] / 30) * (1 + st["late_count"] * 0.2), 1)})
    return sorted(out, key=lambda x: -x["الأولوية"])[:10]


def t_pending_reminders(db, user, a):
    return [{"الفاتورة": r.invoice.number, "العميل": r.customer.name, "المرحلة": r.stage, "النبرة": r.tone, "القناة": r.channel, "الحالة": r.status}
            for r in db.execute(select(Reminder).where(Reminder.status.in_(["draft", "approved"])).order_by(Reminder.id.desc()).limit(15)).scalars()]


def t_settlement_proposals(db, user, a):
    return [{"الفاتورة": p.invoice.number, "العميل": p.invoice.customer.name,
             "الدفعات": [{"n": x["n"], "الاستحقاق": x["due"], "المبلغ": fm(x["amount"])} for x in p.installments], "السبب": p.rationale}
            for p in db.execute(select(SettlementPlan).where(SettlementPlan.status == "proposed")).scalars()]


def t_unmatched_transactions(db, user, a):
    return [{"الرقم": t.id, "التاريخ": t.txn_date.isoformat(), "المبلغ": fm(t.amount), "الوصف": t.description[:80], "الحالة": t.status, "الثقة": t.confidence, "السبب": t.reason}
            for t in db.execute(select(BankTransaction).where(BankTransaction.status.in_(["unmatched", "suggested"])).order_by(BankTransaction.id.desc()).limit(15)).scalars()]


TOOLS = {
    "overdue_invoices": (t_overdue_invoices, "الفواتير المتأخرة مرتبة بالأقدم.", {}),
    "aging_report": (t_aging_report, "تقادم الذمم بالريال العماني (جارية، 1-30، 31-60، 61-90، +90).", {}),
    "customer_statement": (t_customer_statement, "كشف حساب عميل: فواتيره المفتوحة وسلوكه في السداد.", {"name": "اسم العميل أو جزء منه"}),
    "invoice_details": (t_invoice_details, "تفاصيل فاتورة ودفعاتها.", {"number": "رقم الفاتورة مثل INV-2026-0001"}),
    "collection_priorities": (t_collection_priorities, "ترتيب العملاء حسب أولوية التحصيل (المبلغ × التأخر × السوابق).", {}),
    "pending_reminders": (t_pending_reminders, "تذكيرات التحصيل بانتظار الاعتماد أو الإرسال.", {}),
    "settlement_proposals": (t_settlement_proposals, "خطط التسوية المقترحة بانتظار القرار.", {}),
    "unmatched_transactions": (t_unmatched_transactions, "حركات بنكية غير مطابقة أو مقترحة مع سبب كل اقتراح.", {}),
}

AGENTS = {
    "dunning": {
        "name": "وكيل التحصيل والتذكير",
        "tools": ["overdue_invoices", "aging_report", "customer_statement", "invoice_details", "collection_priorities", "pending_reminders", "settlement_proposals"],
        "prompt": "أنت وكيل التحصيل والتذكير في نظام متابعة فواتير الشركات في سلطنة عُمان (الريال العماني بثلاث خانات عشرية). تحدد الأولويات وتشرح وضع كل عميل وتقترح خطوة التحصيل المناسبة. لا ترسل رسائل ولا تغيّر بيانات؛ الإرسال والاعتماد للمحاسب. أجب بالعربية وباختصار واعتمد على نتائج الأدوات فقط.",
        "chips": ["ما الفواتير المتأخرة؟", "من أولى العملاء بالتحصيل؟", "كم تقادم الذمم؟", "ما التذكيرات بانتظار الإرسال؟", "ما خطط التسوية المقترحة؟"],
    },
    "reconciliation": {
        "name": "وكيل المطابقة البنكية",
        "tools": ["unmatched_transactions", "invoice_details", "overdue_invoices", "customer_statement"],
        "prompt": "أنت وكيل المطابقة البنكية في نظام متابعة الفواتير في سلطنة عُمان (الريال العماني). تشرح للمحاسب لماذا طابقت أو اقترحت أو عجزت عن مطابقة كل حركة بنكية، وما الذي يلزم لإكمالها. لا تغيّر بيانات. أجب بالعربية وباختصار واعتمد على نتائج الأدوات فقط.",
        "chips": ["ما الحركات البنكية غير المطابقة؟", "اشرح الفاتورة INV-2026-0001", "ما كشف حساب العميل شركة"],
    },
}


def _run_tool(db, user, name, args):
    try:
        return TOOLS[name][0](db, user, args or {})
    except Exception as e:  # noqa: BLE001
        return {"خطأ": f"تعذّر تنفيذ الأداة ({type(e).__name__})"}


def _specs(agent_key):
    return [{"name": n, "description": TOOLS[n][1], "input_schema": {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in TOOLS[n][2].items()}}}
            for n in AGENTS[agent_key]["tools"]]


def _chat_claude(db, user, agent_key, history, message):
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = AGENTS[agent_key]["prompt"] + f"\nالمستخدم: {user.name}. تاريخ اليوم: {today_om().isoformat()}."
    msgs = [{"role": h["role"], "content": h["content"]} for h in history[-10:] if h.get("role") in ("user", "assistant")] + [{"role": "user", "content": message}]
    trace = []
    for _ in range(6):
        resp = client.messages.create(model=config.AI_MODEL, max_tokens=1200, system=system, tools=_specs(agent_key), messages=msgs)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip(), trace
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = _run_tool(db, user, b.name, b.input) if b.name in AGENTS[agent_key]["tools"] else {"خطأ": "أداة غير مسموحة"}
                trace.append({"tool": b.name, "input": b.input, "result": out})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False, default=str)[:6000]})
        msgs.append({"role": "user", "content": results})
    return "تعذّر إكمال الإجابة ضمن حد الخطوات.", trace


def _chat_local(db, user, agent_key, message):
    m = message.strip()
    num = re.search(r"INV-\d{4}-\d{4}", m, re.I)
    trace = []

    def call(name, **args):
        out = _run_tool(db, user, name, args)
        trace.append({"tool": name, "input": args, "result": out})
        return out

    if num:
        r = call("invoice_details", number=num.group(0))
        if "خطأ" in r:
            return r["خطأ"], trace
        pays = "، ".join(f"{_omr(p['المبلغ'])} ({p['التاريخ']})" for p in r["الدفعات"]) or "لا دفعات"
        late = f" (متأخرة {r['أيام_التأخير']} يوماً)" if r["أيام_التأخير"] else ""
        return (f"{r['الفاتورة']} — {r['العميل']}: الحالة {r['الحالة']}، الإجمالي {_omr(r['الإجمالي'])}، المدفوع {_omr(r['المدفوع'])}، "
                f"المتبقي {_omr(r['المتبقي'])}، الاستحقاق {r['الاستحقاق']}{late}. الدفعات: {pays}."), trace

    def statement():
        name = re.sub(r".*(?:العميل|عميل)\s*", "", m).strip(" ؟?")
        r = call("customer_statement", name=name)
        if "خطأ" in r:
            return r["خطأ"]
        return (f"{r['العميل']}: المستحق {_omr(r['المستحق_الكلي'])}، المتأخر {_omr(r['المتأخر'])}، فواتير مفتوحة {len(r['فواتير_مفتوحة'])}، "
                f"سددت متأخرة {r['فواتير_سددها_متأخراً']} مرة بمتوسط {r['متوسط_التأخر_يوم']} يوماً.")

    if agent_key == "reconciliation":
        if any(w in m for w in ("كشف", "عميل")):
            return statement(), trace
        rows = call("unmatched_transactions")
        return ("حركات بنكية بانتظار المطابقة:\n" + "\n".join(f"• #{r['الرقم']} {r['التاريخ']} {_omr(r['المبلغ'])} — {r['الحالة']} — {r['السبب'] or 'لا مطابقة'}" for r in rows)) if rows else "لا توجد حركات بنكية غير مطابقة.", trace
    if any(w in m for w in ("تقادم", "أعمار", "اعمار")):
        r = call("aging_report")
        return f"تقادم الذمم: جارية {_omr(r['current'])}، 1–30 يوماً {_omr(r['d1_30'])}، 31–60 {_omr(r['d31_60'])}، 61–90 {_omr(r['d61_90'])}، أكثر من 90 {_omr(r['d90_plus'])}.", trace
    if any(w in m for w in ("أولى", "أولوية", "اولوية", "أولويات")):
        rows = call("collection_priorities")
        return ("أولويات التحصيل:\n" + "\n".join(f"• {r['العميل']} — متأخر {_omr(r['المتأخر'])} — أقدم تأخير {r['أقدم_تأخير_يوم']} يوماً — سوابق {r['سوابق_تأخر']}" for r in rows)) if rows else "لا توجد ذمم متأخرة.", trace
    if "تذكير" in m:
        rows = call("pending_reminders")
        return ("تذكيرات بانتظار الإرسال:\n" + "\n".join(f"• {r['الفاتورة']} — {r['العميل']} — {r['النبرة']} ({r['القناة']})" for r in rows)) if rows else "لا توجد تذكيرات بانتظار الإرسال.", trace
    if any(w in m for w in ("تسوية", "خطط", "خطة")):
        rows = call("settlement_proposals")
        if not rows:
            return "لا توجد خطط تسوية مقترحة.", trace
        return "خطط التسوية المقترحة:\n" + "\n".join(f"• {r['الفاتورة']} — {r['العميل']}: " + "، ".join(f"{x['n']}) {_omr(x['المبلغ'])} في {x['الاستحقاق']}" for x in r["الدفعات"]) for r in rows), trace
    if any(w in m for w in ("كشف", "عميل")):
        return statement(), trace
    if any(w in m for w in ("متأخر", "متاخر", "فواتير")):
        rows = call("overdue_invoices")
        return ("الفواتير المتأخرة:\n" + "\n".join(f"• {r['الفاتورة']} — {r['العميل']} — {_omr(r['المتبقي'])} — {r['أيام_التأخير']} يوماً" for r in rows)) if rows else "لا توجد فواتير متأخرة.", trace
    return "أستطيع: عرض الفواتير المتأخرة، وتقادم الذمم، وأولويات التحصيل، والتذكيرات وخطط التسوية المعلّقة، وكشف حساب عميل، وتفاصيل فاتورة بالرقم.", trace


def chat(db: Session, user, agent_key: str, message: str, history: list) -> dict:
    if ai_enabled():
        try:
            reply, trace = _chat_claude(db, user, agent_key, history, message)
            return {"reply": reply, "trace": trace, "mode": "ai"}
        except Exception:  # noqa: BLE001
            pass
    reply, trace = _chat_local(db, user, agent_key, message)
    return {"reply": reply, "trace": trace, "mode": "rules"}
