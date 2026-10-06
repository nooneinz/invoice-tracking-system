import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, omr, dateAr, INV_STATUS, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'

export default function Invoices() {
  const user = useAuth()
  const [sp, setSp] = useSearchParams()
  const status = sp.get('status') || ''
  const [q, setQ] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => { setRows(null); api(`/invoices?status=${status}&q=${encodeURIComponent(q)}`).then(setRows) }, [status, q])
  const tabs = [['', 'الكل'], ['overdue', 'متأخرة'], ['issued', 'صادرة'], ['partial', 'جزئية'], ['paid', 'مسددة'], ['draft', 'مسودات']]
  const total = (rows || []).reduce((s, r) => s + r.balance, 0)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold flex-1">الفواتير</h1>{canWrite(user) && <Link to="/invoices/new" className="btn btn-primary">فاتورة جديدة</Link>}</div>
      <div className="flex flex-wrap gap-2 items-center">{tabs.map(([k, l]) => <button key={k} className={`btn ${status === k ? 'btn-primary' : 'btn-ghost'} !min-h-[40px]`} onClick={() => setSp(k ? { status: k } : {})}>{l}</button>)}
        <label className="sr-only" htmlFor="q">بحث</label><input id="q" className="input !w-56 ms-auto" placeholder="رقم الفاتورة أو العميل" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="card !p-0 overflow-x-auto"><table className="w-full min-w-[780px]">
        <thead><tr><th className="th">الرقم</th><th className="th">العميل</th><th className="th">الإصدار</th><th className="th">الاستحقاق</th><th className="th">الإجمالي</th><th className="th">المتبقي</th><th className="th">الحالة</th></tr></thead>
        <tbody>
          {rows === null && <tr><td className="td" colSpan="7">جارٍ التحميل…</td></tr>}
          {rows && rows.length === 0 && <tr><td className="td text-muted" colSpan="7">لا توجد فواتير مطابقة.</td></tr>}
          {(rows || []).map((i) => (
            <tr key={i.id} className="hover:bg-brand-50/50">
              <td className="td font-semibold"><Link className="underline text-brand-800 num" to={`/invoices/${i.id}`}>{i.number}</Link></td><td className="td">{i.customer}</td>
              <td className="td text-sm">{dateAr(i.issue_date)}</td><td className="td text-sm">{dateAr(i.due_date)}{i.days_overdue > 0 && <div className="text-xs text-bad">متأخرة {i.days_overdue} يوماً</div>}</td>
              <td className="td num">{omr(i.total)}</td><td className="td num font-semibold">{omr(i.balance)}</td>
              <td className="td"><span className={`badge ${INV_STATUS[i.status][1]}`}>{INV_STATUS[i.status][0]}</span></td></tr>))}
        </tbody>
        {rows && rows.length > 0 && <tfoot><tr><td className="td font-bold" colSpan="5">إجمالي المتبقي في القائمة</td><td className="td num font-bold" colSpan="2">{omr(total)}</td></tr></tfoot>}
      </table></div>
    </div>
  )
}
