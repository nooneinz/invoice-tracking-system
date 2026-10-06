import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'
import { api, omr, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../layout.jsx'

const AGE = [['current', 'جارية', '#1f6b4a'], ['d1_30', '1–30', '#c58a00'], ['d31_60', '31–60', '#d9622b'], ['d61_90', '61–90', '#b42318'], ['d90_plus', '+90', '#7b1e2e']]

function Kpi({ label, value, sub, tone = '', to }) {
  const body = <div className="card h-full hover:border-brand-700 transition-colors"><div className="text-sm text-muted">{label}</div><div className={`font-display text-2xl font-bold mt-1 num ${tone}`}>{value}</div>{sub && <div className="text-xs text-muted mt-1">{sub}</div>}</div>
  return to ? <Link to={to}>{body}</Link> : body
}

export default function Dashboard() {
  const user = useAuth()
  const [d, setD] = useState(null)
  useEffect(() => { api('/dashboard').then(setD) }, [])
  if (!d) return <p>جارٍ التحميل…</p>
  const age = AGE.map(([k, l, c]) => ({ name: l, value: d.aging[k], color: c }))
  const empty = d.open_count === 0 && d.trend.every((t) => !t.issued && !t.collected)
  const actions = [['mail', 'تذكيرات بانتظار الاعتماد', d.pending_reminders, '/collections'], ['coin', 'خطط تسوية مقترحة', d.pending_plans, '/collections'], ['bank', 'حركات بنكية للمراجعة', d.bank_to_review, '/bank']]
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold flex-1">لوحة التحصيل</h1>
        {canWrite(user) && <Link to="/invoices/new" className="btn btn-primary"><Icon name="receipt" size={18} /> فاتورة جديدة</Link>}</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="إجمالي المستحق" value={omr(d.outstanding)} sub={`${d.open_count} فاتورة مفتوحة`} to="/invoices" />
        <Kpi label="المتأخر" value={omr(d.overdue)} sub={`${d.overdue_count} فاتورة`} tone={d.overdue_count ? 'text-bad' : ''} to="/invoices?status=overdue" />
        <Kpi label="المحصّل هذا الشهر" value={omr(d.collected_month)} tone="text-ok" />
        <Kpi label="متوسط أيام التحصيل" value={d.dso === null ? '—' : `${d.dso} يوماً`} sub="من الإصدار إلى آخر دفعة" />
      </div>
      {empty && <p className="card text-muted">لا توجد فواتير بعد. ابدأ بإضافة عميل ثم أصدر أول فاتورة، وستظهر هنا الأعمار والاتجاهات.</p>}
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="card"><h2 className="font-bold mb-3">تقادم الذمم (ر.ع)</h2>
          <div style={{ height: 250 }} dir="ltr"><ResponsiveContainer><BarChart data={age}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" /><YAxis /><Tooltip formatter={(v) => omr(v)} />
            <Bar dataKey="value" name="المبلغ" radius={[6, 6, 0, 0]}>{age.map((a) => <Cell key={a.name} fill={a.color} />)}</Bar></BarChart></ResponsiveContainer></div></section>
        <section className="card"><h2 className="font-bold mb-3">المُصدَر مقابل المحصّل — 6 أشهر (ر.ع)</h2>
          <div style={{ height: 250 }} dir="ltr"><ResponsiveContainer><LineChart data={d.trend}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" tickFormatter={(v) => v.slice(5)} /><YAxis /><Tooltip formatter={(v) => omr(v)} /><Legend />
            <Line dataKey="issued" name="مُصدَر" stroke="#7b1e2e" strokeWidth={3} dot /><Line dataKey="collected" name="محصّل" stroke="#1f6b4a" strokeWidth={3} dot /></LineChart></ResponsiveContainer></div></section>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="card"><h2 className="font-bold mb-3">يحتاج إجراءً منك</h2>
          <ul className="divide-y divide-line">{actions.map(([i, l, n, to]) => (
            <li key={l}><Link to={to} className="flex items-center gap-3 py-3 hover:text-brand-800"><Icon name={i} size={20} className="text-brand-800" /><span className="flex-1">{l}</span><b className={`num ${n ? 'text-bad' : 'text-muted'}`}>{n}</b></Link></li>))}</ul>
          {!d.smtp && <p className="text-xs text-warn mt-3">البريد غير مضبوط (SMTP): تبقى رسائل البريد مسودات حتى تُضبط، وتعمل رسائل واتساب بنقرة.</p>}</section>
        <section className="card"><h2 className="font-bold mb-3">أكبر المتأخرين</h2>
          {d.top_overdue.length === 0 ? <p className="text-muted text-sm">لا توجد ذمم متأخرة.</p> : (
            <ul className="divide-y divide-line">{d.top_overdue.map((c) => <li key={c.id} className="flex justify-between py-2.5"><Link className="underline text-brand-800" to={`/customers?id=${c.id}`}>{c.name}</Link><b className="num text-bad">{omr(c.amount)}</b></li>)}</ul>)}</section>
      </div>
    </div>
  )
}
