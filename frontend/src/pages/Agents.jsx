import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, dateAr } from '../api.js'
import ChatPanel from '../ChatPanel.jsx'

const Num = ({ label, value, tone = '' }) => <div className="rounded-lg bg-brand-50 p-3 text-center"><div className={`text-2xl font-bold num ${tone}`}>{value}</div><div className="text-xs text-muted">{label}</div></div>

export default function Agents() {
  const [d, setD] = useState(null)
  const [cat, setCat] = useState(null)
  useEffect(() => { api('/agents/catalog').then(setCat); const load = () => api('/agents/overview').then(setD); load(); const t = setInterval(load, 10000); return () => clearInterval(t) }, [])
  if (!d) return <p>جارٍ التحميل…</p>
  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold">وكلاء الذكاء الاصطناعي</h1>
      {cat && <ChatPanel agents={cat} aiEnabled={d.ai_enabled} model={d.model} />}
      <div className="grid md:grid-cols-2 gap-4">
        <section className="card space-y-4"><div className="flex items-center gap-2"><h2 className="font-bold text-lg flex-1">وكيل التحصيل والتذكير</h2><span className="badge bg-emerald-100 text-emerald-900">فعّال</span></div>
          <p className="text-sm text-muted leading-7">يولّد تذكيرات قبل الاستحقاق وبعده بنبرة تتكيّف مع سجل كل عميل، ويقترح خطط تسوية للمتأخرات، ويراقب التزام العميل بالخطة. تبقى الرسائل مسودات لاعتمادك.</p>
          <div className="grid grid-cols-4 gap-2"><Num label="بانتظار" value={d.reminders.draft + d.reminders.approved} tone="text-warn" /><Num label="أُرسلت" value={d.reminders.sent} tone="text-ok" /><Num label="فشلت" value={d.reminders.failed} tone="text-bad" /><Num label="خطط مقترحة" value={d.plans.proposed} /></div>
          <div className="text-sm">خطط سارية <b>{d.plans.active}</b> · مكتملة <b>{d.plans.completed}</b> · متعثرة <b className="text-bad">{d.plans.defaulted}</b></div>
          <p className="text-xs text-muted">{d.smtp ? 'SMTP مضبوط: تُرسل الرسائل المعتمدة بالبريد مع الفاتورة PDF.' : 'SMTP غير مضبوط: تبقى رسائل البريد مسودات، وتعمل رسائل واتساب بنقرة.'}</p>
          <Link to="/collections" className="btn btn-primary">فتح التحصيل</Link></section>
        <section className="card space-y-4"><div className="flex items-center gap-2"><h2 className="font-bold text-lg flex-1">وكيل المطابقة البنكية</h2><span className="badge bg-emerald-100 text-emerald-900">فعّال</span></div>
          <p className="text-sm text-muted leading-7">يطابق التحويلات الواردة مع الفواتير المفتوحة برقم الفاتورة أو اسم العميل والمبلغ، ويغلق المسددة تلقائياً عند ثقة 90%+ ويقترح الباقي مع سببه.</p>
          <div className="grid grid-cols-4 gap-2"><Num label="مطابقة" value={d.bank.matched} tone="text-ok" /><Num label="اقتراحات" value={d.bank.suggested} tone="text-warn" /><Num label="بلا مطابقة" value={d.bank.unmatched} tone="text-bad" /><Num label="متجاهَلة" value={d.bank.ignored} /></div>
          <Link to="/bank" className="btn btn-primary">فتح المطابقة</Link></section>
      </div>
      {d.activity.length > 0 && <section className="card"><h2 className="font-bold mb-3">نشاط الوكلاء</h2><ul className="space-y-3">{d.activity.map((a) => <li key={a.id} className="flex gap-3 items-start"><span className="badge bg-brand-50 text-brand-800 mt-1 whitespace-nowrap">{a.agent}</span><div className="text-sm"><div>{a.details}</div><div className="text-xs text-muted">{dateAr(a.ts)}</div></div></li>)}</ul></section>}
    </div>
  )
}
