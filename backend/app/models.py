"""كل المبالغ أعداد صحيحة بالبيسة (1 ر.ع = 1000 بيسة) لحسابات حتمية بلا أخطاء فاصلة عائمة."""
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, ForeignKey, Text, JSON, UniqueConstraint, BigInteger, Index
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base
from . import config

ROLES = ["admin", "finance", "viewer"]
OM_TZ = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))


def now_om() -> datetime:
    return datetime.now(OM_TZ).replace(tzinfo=None, microsecond=0)


def today_om() -> date:
    return now_om().date()


def to_b(omr) -> int:
    return int(round(float(omr) * 1000))


def fm(b) -> float:
    return round((b or 0) / 1000, 3)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="finance")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    email: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    vatin: Mapped[str] = mapped_column(String(40), default="")
    cr_number: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(250), default="")
    credit_days: Mapped[int] = mapped_column(Integer, default=30)
    preferred_channel: Mapped[str] = mapped_column(String(12), default="email")  # email|whatsapp
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)  # draft|issued|partial|paid|void
    vat_rate: Mapped[float] = mapped_column(Float, default=5.0)
    subtotal: Mapped[int] = mapped_column(BigInteger, default=0)
    vat_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    paid: Mapped[int] = mapped_column(BigInteger, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer = relationship("Customer", lazy="joined")
    items = relationship("InvoiceItem", cascade="all, delete-orphan", lazy="selectin", order_by="InvoiceItem.id")
    payments = relationship("Payment", cascade="all, delete-orphan", lazy="selectin", order_by="Payment.id")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(String(250))
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[int] = mapped_column(BigInteger, default=0)


class Payment(Base):
    __tablename__ = "payments"
    # المرجع فريد لإشعارات بوابة الدفع فقط (منع التكرار)؛ شيك واحد قد يسدد عدة فواتير يدوياً
    __table_args__ = (Index("uq_payment_webhook_ref", "reference", unique=True, sqlite_where=text("source = 'webhook'"), postgresql_where=text("source = 'webhook'")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(20), default="bank_transfer")
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    received_at: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|bank_import|webhook
    bank_txn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(250), default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_bank_fp"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    txn_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(300), default="")
    reference: Mapped[str] = mapped_column(String(120), default="")
    counterparty: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(12), default="unmatched", index=True)  # unmatched|suggested|matched|ignored
    confidence: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(String(300), default="")
    suggestion: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{invoice_id, amount}]
    matched_by: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("invoice_id", "stage", name="uq_reminder_stage"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    stage: Mapped[str] = mapped_column(String(20))
    tone: Mapped[str] = mapped_column(String(10), default="neutral")
    channel: Mapped[str] = mapped_column(String(12), default="email")
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(14), default="draft", index=True)  # draft|approved|sent|failed|skipped
    error: Mapped[str] = mapped_column(String(300), default="")
    mode: Mapped[str] = mapped_column(String(8), default="rules")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    invoice = relationship("Invoice", lazy="joined")
    customer = relationship("Customer", lazy="joined")


class SettlementPlan(Base):
    __tablename__ = "settlement_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed|active|rejected|completed|defaulted
    installments: Mapped[list] = mapped_column(JSON)  # [{n, due, amount}]
    rationale: Mapped[str] = mapped_column(Text, default="")
    paid_at_start: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_om)
    decided_by: Mapped[str] = mapped_column(String(120), default="")
    invoice = relationship("Invoice", lazy="joined")


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), index=True)
    started: Mapped[datetime] = mapped_column(DateTime, default=now_om)
    finished: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="running")
    detail: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(20), default="schedule")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now_om)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")
