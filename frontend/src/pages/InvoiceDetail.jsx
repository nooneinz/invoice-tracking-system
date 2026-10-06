import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, omr, dateAr, openPdf, INV_STATUS, TONE, REM_STATUS, stageLabel, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../layout.jsx'

export default function InvoiceDetail() {
  const { id } = useParams()
  const user = useAuth()
  const [i, setI] = useState(null)
  const [err, setErr] = useState('')
  const [pay, setPay] = useState({ amount: '', method: 'bank_transfer', reference: '', received_at: '' })
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => api(`/invoices/${id}`).then(setI).catch((e) => setErr(e.message)), [id])
  useEffect(() => { load() }, [load])
  const act = async (fn) => { setBusy(true); setErr(''); try { await fn(); await load() } catch (e) { setErr(e.message) } finally { setBusy(false) } }
  if (err && !i) return <p role="alert" className="text-bad">{err}</p>
  if (!i) return <p>جارٍ التحميل…</p>
  const open = ['issued', 'partial', 'overdue'].includes(i.status)
  const st = INV_STATUS[i.status]
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1"><h1 className="font-display text-2xl font-bold num">{i.number}</h1><Link className="text-sm underline text-brand-800" to={`/customers?id=${i.customer_id}`}>{i.customer}</Link></div>
        <span className={`badge ${st[1]} !text-sm`}>{st[0]}{i.days_overdue > 0 && ` — ${i.days_overdue} يوماً`}</span>
        {i.base_status !== 'draft' && <button className="btn btn-ghost" onClick={() => openPdf(i.id).catch((e) => setErr(e.message))}><Icon name="download" size={18} /> PDF</button>}
        {i.base_status === 'draft' && canWrite(user) && <><Link to={`/invoices/${i.id}/edit`} className="btn btn-ghost">تعديل</Link><button className="btn btn-primary" disabled={busy} onClick={() => act(() => api(`/invoices/${id}/issue`, { method: 'POST' }))}>إصدار الفاتورة</button></>}
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="card"><div className="text-xs text-muted">الإجمالي</div><div className="font-display font-bold text-xl num">{omr(i.total)}</div></div>
        <div className="card"><div className="text-xs text-muted">المدفوع</div><div className="font-display font-bold text-xl num text-ok">{omr(i.paid)}</div></div>
        <div className="card"><div className="text-xs text-muted">المتبقي</div><div className={`font-display font-bold text-xl num ${i.balance > 0 && i.days_overdue ? 'text-bad' : ''}`}>{omr(i.balance)}</div></div>
        <div className="card"><div className="text-xs text-muted">الاستحقاق</div><div className="font-bold">{dateAr(i.due_date)}</div><div className="text-xs text-muted">الإصدار {dateAr(i.issue_date)}</div></div>
      </div>

      <section className="card !p-0 overflow-x-auto"><table className="w-full min-w-[520px]"><thead><tr><th className="th">الوصف</th><th className="th">الكمية</th><th className="th">سعر الوحدة</th><th className="th">الإجمالي</th></tr></thead>
        <tbody>{i.items.map((x) => <tr key={x.id}><td className="td">{x.description}</td><td className="td num">{x.quantity}</td><td className="td num">{omr(x.unit_price)}</td><td className="td num">{omr(x.line_total)}</td></tr>)}</tbody>
        <tfoot><tr><td className="td text-muted" colSpan="3">المجموع قبل الضريبة</td><td className="td num">{omr(i.subtotal)}</td></tr><tr><td className="td text-muted" colSpan="3">ضريبة القيمة المضافة {i.vat_rate}%</td><td className="td num">{omr(i.vat_amount)}</td></tr><tr><td className="td font-bold" colSpan="3">الإجمالي</td><td className="td num font-bold">{omr(i.total)}</td></tr></tfoot></table></section>

      <section className="card space-y-3"><h2 className="font-bold">الدفعات</h2>
        {i.payments.length === 0 ? <p className="text-muted text-sm">لا توجد دفعات بعد.</p> : (
          <ul className="divide-y divide-line">{i.payments.map((p) => <li key={p.id} className="py-2.5 flex flex-wrap gap-x-4 gap-y-1 items-center"><b className="num">{omr(p.amount)}</b><span className="text-sm">{dateAr(p.received_at)}</span><span className="text-sm text-muted">{{ bank_transfer: 'تحويل بنكي', cash: 'نقداً', cheque: 'شيك', card: 'بطاقة' }[p.method]}</span>{p.reference && <span className="text-xs num text-muted">{p.reference}</span>}<span className="badge bg-slate-100 text-slate-700 ms-auto">{{ manual: 'يدوي', bank_import: 'مطابقة بنكية', webhook: 'بوابة الدفع' }[p.source]}</span></li>)}</ul>)}
        {open && canWrite(user) && (
          <form className="grid md:grid-cols-5 gap-3 items-end border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); act(async () => { await api(`/invoices/${id}/payments`, { method: 'POST', body: { amount: Number(pay.amount), method: pay.method, reference: pay.reference, received_at: pay.received_at || null } }); setPay({ amount: '', method: 'bank_transfer', reference: '', received_at: '' }) }) }}>
            <div><label className="lbl" htmlFor="pa">المبلغ (ر.ع)</label><input id="pa" className="input num" type="number" step="0.001" min="0.001" max={i.balance} required value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} /></div>
            <div><label className="lbl" htmlFor="pm">الطريقة</label><select id="pm" className="input" value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })}><option value="bank_transfer">تحويل بنكي</option><option value="cash">نقداً</option><option value="cheque">شيك</option><option value="card">بطاقة</option></select></div>
            <div><label className="lbl" htmlFor="pr">المرجع</label><input id="pr" className="input" value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} /></div>
            <div><label className="lbl" htmlFor="pd">تاريخ الاستلام</label><input id="pd" className="input" type="date" value={pay.received_at} onChange={(e) => setPay({ ...pay, received_at: e.target.value })} /></div>
            <button className="btn btn-primary" disabled={busy}>تسجيل الدفعة</button></form>)}
      </section>

      {i.plans.length > 0 && <section className="card space-y-3"><h2 className="font-bold">خطط التسوية</h2>{i.plans.map((p) => (
        <div key={p.id} className="border border-line rounded-lg p-3"><div className="flex gap-2 items-center mb-1"><span className="badge bg-brand-50 text-brand-800">{{ proposed: 'مقترحة', active: 'سارية', completed: 'مكتملة', defaulted: 'متعثرة', rejected: 'مرفوضة' }[p.status]}</span><span className="text-sm text-muted">{p.rationale}</span></div>
          <ol className="text-sm grid sm:grid-cols-2 gap-1">{p.installments.map((x) => <li key={x.n}>الدفعة {x.n}: <b className="num">{omr(x.amount)}</b> بتاريخ {dateAr(x.due)}</li>)}</ol></div>))}<Link to="/collections" className="text-sm underline text-brand-800">اعتماد الخطط من صفحة التحصيل</Link></section>}

      {i.reminders.length > 0 && <section className="card space-y-2"><h2 className="font-bold">سجل التذكيرات</h2>{i.reminders.map((r) => (
        <div key={r.id} className="flex flex-wrap gap-2 items-center text-sm border-b border-line pb-2 last:border-0"><span className={`badge ${TONE[r.tone][1]}`}>{TONE[r.tone][0]}</span><b>{stageLabel(r.stage)}</b><span className="text-muted">{r.channel === 'email' ? 'بريد' : 'واتساب'}</span><span className={`badge ${REM_STATUS[r.status][1]} ms-auto`}>{REM_STATUS[r.status][0]}</span></div>))}</section>}

      {i.notes && <p className="card text-sm"><b>ملاحظات: </b>{i.notes}</p>}
      {canWrite(user) && ['issued', 'draft'].includes(i.base_status) && i.paid === 0 && <button className="btn btn-ghost text-bad" disabled={busy} onClick={() => { const r = window.prompt('سبب إلغاء الفاتورة'); if (r) act(() => api(`/invoices/${id}/void`, { method: 'POST', body: { reason: r } })) }}>إلغاء الفاتورة</button>}
      {err && <p role="alert" className="text-bad font-semibold">{err}</p>}
    </div>
  )
}
