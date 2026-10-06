import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, omr } from '../api.js'

const today = () => new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10)

export default function InvoiceEditor() {
  const { id } = useParams()
  const nav = useNavigate()
  const [customers, setCustomers] = useState([])
  const [settings, setSettings] = useState({ vat_rate: '5', company_name: '' })
  const [f, setF] = useState({ customer_id: '', issue_date: today(), due_date: '', notes: '' })
  const [items, setItems] = useState([{ description: '', quantity: 1, unit_price: '' }])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api('/customers').then(setCustomers); api('/settings').then(setSettings)
    if (id) api(`/invoices/${id}`).then((i) => { setF({ customer_id: i.customer_id, issue_date: i.issue_date, due_date: i.due_date, notes: i.notes }); setItems(i.items.map((x) => ({ description: x.description, quantity: x.quantity, unit_price: x.unit_price }))) })
  }, [id])
  const cust = customers.find((c) => c.id === Number(f.customer_id))
  const dueAuto = useMemo(() => { if (!cust) return ''; const d = new Date(f.issue_date + 'T00:00:00'); d.setDate(d.getDate() + cust.credit_days); return d.toISOString().slice(0, 10) }, [cust, f.issue_date])
  const due = f.due_date || dueAuto
  const t = useMemo(() => {
    const sub = items.reduce((s, l) => s + Math.round(Number(l.quantity || 0) * Math.round(Number(l.unit_price || 0) * 1000)), 0)
    const vat = Math.round(sub * Number(settings.vat_rate) / 100)
    return { sub: sub / 1000, vat: vat / 1000, total: (sub + vat) / 1000 }
  }, [items, settings.vat_rate])
  const set = (i, k, v) => setItems(items.map((x, j) => (j === i ? { ...x, [k]: v } : x)))

  const save = async (issue) => {
    setBusy(true); setErr('')
    try {
      const body = { customer_id: Number(f.customer_id), issue_date: f.issue_date, due_date: due || null, notes: f.notes, items: items.map((x) => ({ description: x.description, quantity: Number(x.quantity), unit_price: Number(x.unit_price || 0) })) }
      const inv = id ? await api(`/invoices/${id}`, { method: 'PUT', body }) : await api('/invoices', { method: 'POST', body })
      if (issue) await api(`/invoices/${inv.id}/issue`, { method: 'POST' })
      nav(`/invoices/${inv.id}`)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-5">
      <h1 className="font-display text-2xl font-bold">{id ? 'تعديل مسودة' : 'فاتورة جديدة'}</h1>
      <div className="grid xl:grid-cols-[1fr_380px] gap-6 items-start">
        <form onSubmit={(e) => { e.preventDefault(); save(false) }} className="space-y-4">
          <div className="card grid md:grid-cols-3 gap-4">
            <div className="md:col-span-3"><label className="lbl" htmlFor="c">العميل</label><select id="c" className="input" required value={f.customer_id} onChange={(e) => setF({ ...f, customer_id: e.target.value, due_date: '' })}><option value="">اختر العميل…</option>{customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
            <div><label className="lbl" htmlFor="i">تاريخ الإصدار</label><input id="i" type="date" className="input" required value={f.issue_date} onChange={(e) => setF({ ...f, issue_date: e.target.value })} /></div>
            <div><label className="lbl" htmlFor="d">تاريخ الاستحقاق</label><input id="d" type="date" className="input" min={f.issue_date} value={due} onChange={(e) => setF({ ...f, due_date: e.target.value })} />{cust && <p className="text-xs text-muted mt-1">مهلة العميل {cust.credit_days} يوماً</p>}</div>
          </div>
          <div className="card space-y-3"><h2 className="font-bold">البنود</h2>
            {items.map((x, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-end">
                <div className="col-span-12 md:col-span-6"><label className="lbl" htmlFor={`d${i}`}>الوصف</label><input id={`d${i}`} className="input" required value={x.description} onChange={(e) => set(i, 'description', e.target.value)} /></div>
                <div className="col-span-5 md:col-span-2"><label className="lbl" htmlFor={`q${i}`}>الكمية</label><input id={`q${i}`} className="input num" type="number" min="0.001" step="any" required value={x.quantity} onChange={(e) => set(i, 'quantity', e.target.value)} /></div>
                <div className="col-span-5 md:col-span-3"><label className="lbl" htmlFor={`p${i}`}>سعر الوحدة (ر.ع)</label><input id={`p${i}`} className="input num" type="number" min="0" step="0.001" required value={x.unit_price} onChange={(e) => set(i, 'unit_price', e.target.value)} /></div>
                <div className="col-span-2 md:col-span-1">{items.length > 1 && <button type="button" className="btn btn-ghost w-full" aria-label="حذف البند" onClick={() => setItems(items.filter((_, j) => j !== i))}>✕</button>}</div>
              </div>))}
            <button type="button" className="btn btn-ghost" onClick={() => setItems([...items, { description: '', quantity: 1, unit_price: '' }])}>+ إضافة بند</button></div>
          <div className="card"><label className="lbl" htmlFor="n">ملاحظات تظهر في الفاتورة</label><textarea id="n" className="input" rows="2" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></div>
          {err && <p role="alert" className="text-bad font-semibold">{err}</p>}
          <div className="flex flex-wrap gap-2"><button className="btn btn-ghost" disabled={busy || !f.customer_id}>حفظ كمسودة</button><button type="button" className="btn btn-primary" disabled={busy || !f.customer_id} onClick={() => { if (document.querySelector('form').reportValidity()) save(true) }}>حفظ وإصدار الفاتورة</button></div>
        </form>

        <aside className="xl:sticky xl:top-6" aria-label="معاينة الفاتورة">
          <div className="sheet bg-white border border-line rounded-xl p-5 space-y-3">
            <div className="flex justify-between"><div><div className="font-display font-bold text-brand-800">فاتورة ضريبية</div><div className="text-xs text-muted">{id ? 'مسودة' : 'رقم تلقائي عند الحفظ'}</div></div><span className="badge bg-sky-100 text-sky-900">معاينة مباشرة</span></div>
            <div className="text-sm"><div className="text-muted text-xs">من</div><b>{settings.company_name}</b></div>
            <div className="text-sm"><div className="text-muted text-xs">إلى</div><b>{cust ? cust.name : '—'}</b></div>
            <div className="grid grid-cols-2 text-sm gap-2"><div><div className="text-muted text-xs">الإصدار</div><span className="num">{f.issue_date}</span></div><div><div className="text-muted text-xs">الاستحقاق</div><b className="num text-brand-800">{due || '—'}</b></div></div>
            <table className="w-full text-sm"><tbody>{items.filter((x) => x.description).map((x, i) => <tr key={i} className="border-t border-line"><td className="py-1.5">{x.description}<div className="text-xs text-muted num">{x.quantity} × {Number(x.unit_price || 0).toFixed(3)}</div></td><td className="num text-end">{(Number(x.quantity || 0) * Number(x.unit_price || 0)).toFixed(3)}</td></tr>)}</tbody></table>
            <dl className="text-sm space-y-1 border-t border-line pt-2"><div className="flex justify-between"><dt className="text-muted">قبل الضريبة</dt><dd className="num">{t.sub.toFixed(3)}</dd></div><div className="flex justify-between"><dt className="text-muted">ضريبة {settings.vat_rate}%</dt><dd className="num">{t.vat.toFixed(3)}</dd></div>
              <div className="flex justify-between font-bold text-base text-brand-800"><dt>الإجمالي</dt><dd className="num">{omr(t.total)}</dd></div></dl>
          </div>
        </aside>
      </div>
    </div>
  )
}
