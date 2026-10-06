import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, omr, dateAr, INV_STATUS, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'

const blank = { name: '', email: '', phone: '', contact_name: '', vatin: '', cr_number: '', address: '', credit_days: 30, preferred_channel: 'email' }

export default function Customers() {
  const user = useAuth()
  const [sp, setSp] = useSearchParams()
  const sel = sp.get('id')
  const [rows, setRows] = useState([])
  const [st, setSt] = useState(null)
  const [f, setF] = useState(blank)
  const [show, setShow] = useState(false)
  const [err, setErr] = useState('')
  const load = () => api('/customers').then(setRows)
  useEffect(() => { load() }, [])
  useEffect(() => { setSt(null); if (sel) api(`/customers/${sel}/statement`).then(setSt) }, [sel])
  const add = async (e) => {
    e.preventDefault(); setErr('')
    try { await api('/customers', { method: 'POST', body: { ...f, credit_days: Number(f.credit_days) } }); setF(blank); setShow(false); load() } catch (x) { setErr(x.message) }
  }
  if (sel && st) return (
    <div className="space-y-4">
      <button className="btn btn-ghost" onClick={() => setSp({})}>← العملاء</button>
      <h1 className="font-display text-2xl font-bold">{st.customer.name}</h1>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="card"><div className="text-xs text-muted">المستحق</div><b className="num text-xl">{omr(st.stats.outstanding)}</b></div>
        <div className="card"><div className="text-xs text-muted">المتأخر</div><b className={`num text-xl ${st.stats.overdue_amount ? 'text-bad' : ''}`}>{omr(st.stats.overdue_amount)}</b></div>
        <div className="card"><div className="text-xs text-muted">فواتير سُدّدت متأخرة</div><b className="text-xl">{st.stats.late_count}</b><div className="text-xs text-muted">بمتوسط {st.stats.avg_days_late} يوماً</div></div>
        <div className="card"><div className="text-xs text-muted">الاتصال</div><div className="text-sm">{st.customer.contact_name || '—'}</div><div className="text-xs text-muted num" dir="ltr">{st.customer.email} {st.customer.phone}</div><div className="text-xs">قناة التذكير: {st.customer.preferred_channel === 'email' ? 'البريد' : 'واتساب'}</div></div>
      </div>
      <div className="card !p-0 overflow-x-auto"><table className="w-full min-w-[640px]"><thead><tr><th className="th">الفاتورة</th><th className="th">الإصدار</th><th className="th">الاستحقاق</th><th className="th">الإجمالي</th><th className="th">المتبقي</th><th className="th">الحالة</th></tr></thead>
        <tbody>{st.invoices.length === 0 && <tr><td className="td text-muted" colSpan="6">لا توجد فواتير.</td></tr>}{st.invoices.map((i) => <tr key={i.id}><td className="td"><Link className="underline text-brand-800 num" to={`/invoices/${i.id}`}>{i.number}</Link></td><td className="td text-sm">{dateAr(i.issue_date)}</td><td className="td text-sm">{dateAr(i.due_date)}</td><td className="td num">{omr(i.total)}</td><td className="td num">{omr(i.balance)}</td><td className="td"><span className={`badge ${INV_STATUS[i.status][1]}`}>{INV_STATUS[i.status][0]}</span></td></tr>)}</tbody></table></div>
    </div>
  )
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold flex-1">العملاء</h1>{canWrite(user) && <button className="btn btn-primary" onClick={() => setShow(!show)}>{show ? 'إغلاق' : 'عميل جديد'}</button>}</div>
      {show && (
        <form onSubmit={add} className="card grid md:grid-cols-4 gap-3 items-end">
          <div className="md:col-span-2"><label className="lbl" htmlFor="cn">اسم الشركة</label><input id="cn" className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="cc">جهة الاتصال</label><input id="cc" className="input" value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="cd">مهلة السداد (يوم)</label><input id="cd" className="input" type="number" min="0" max="365" value={f.credit_days} onChange={(e) => setF({ ...f, credit_days: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="ce">البريد</label><input id="ce" className="input" type="email" dir="ltr" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="cp">الجوال</label><input id="cp" className="input" dir="ltr" placeholder="9XXX XXXX" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="cv">الرقم الضريبي (VATIN)</label><input id="cv" className="input" dir="ltr" value={f.vatin} onChange={(e) => setF({ ...f, vatin: e.target.value })} /></div>
          <div><label className="lbl" htmlFor="ch">قناة التذكير</label><select id="ch" className="input" value={f.preferred_channel} onChange={(e) => setF({ ...f, preferred_channel: e.target.value })}><option value="email">البريد</option><option value="whatsapp">واتساب</option></select></div>
          <div className="md:col-span-3"><label className="lbl" htmlFor="ca">العنوان</label><input id="ca" className="input" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></div>
          <button className="btn btn-primary">حفظ العميل</button>{err && <p role="alert" className="text-bad md:col-span-4">{err}</p>}
        </form>)}
      <div className="card !p-0 overflow-x-auto"><table className="w-full min-w-[640px]"><thead><tr><th className="th">العميل</th><th className="th">الاتصال</th><th className="th">المستحق</th><th className="th">المتأخر</th><th className="th">سجل السداد</th></tr></thead>
        <tbody>{rows.length === 0 && <tr><td className="td text-muted" colSpan="5">لا يوجد عملاء بعد.</td></tr>}{rows.map((c) => (
          <tr key={c.id} className="hover:bg-brand-50/50"><td className="td font-semibold"><button className="underline text-brand-800" onClick={() => setSp({ id: c.id })}>{c.name}</button></td><td className="td text-sm" dir="ltr">{c.email || c.phone || '—'}</td>
            <td className="td num">{omr(c.outstanding)}</td><td className={`td num ${c.overdue_amount ? 'text-bad font-semibold' : ''}`}>{omr(c.overdue_amount)}</td><td className="td text-sm">{c.late_count ? `تأخر ${c.late_count} مرة (متوسط ${c.avg_days_late} يوماً)` : 'منتظم'}</td></tr>))}</tbody></table></div>
    </div>
  )
}
