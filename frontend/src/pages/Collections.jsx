import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, omr, dateAr, TONE, REM_STATUS, stageLabel, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'
import { Icon } from '../layout.jsx'

function Reminder({ r, onChange, can }) {
  const [edit, setEdit] = useState(false)
  const [body, setBody] = useState(r.body)
  const [err, setErr] = useState('')
  const act = async (a) => { setErr(''); try { await api(`/reminders/${r.id}/${a}`, { method: 'POST' }); onChange() } catch (e) { setErr(e.message); onChange() } }
  const save = async () => { await api(`/reminders/${r.id}`, { method: 'PATCH', body: { body } }); setEdit(false); onChange() }
  const wa = r.whatsapp_phone ? `https://wa.me/${r.whatsapp_phone}?text=${encodeURIComponent(r.body)}` : null
  const actionable = ['draft', 'approved', 'failed'].includes(r.status)
  return (
    <article className="card space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/invoices/${r.invoice_id}`} className="font-bold underline text-brand-800 num">{r.invoice}</Link><span>{r.customer}</span>
        <span className={`badge ${TONE[r.tone][1]}`}>نبرة {TONE[r.tone][0]}</span><span className="badge bg-slate-100 text-slate-700">{stageLabel(r.stage)}</span>
        <span className="badge bg-slate-100 text-slate-700">{r.channel === 'email' ? 'بريد' : 'واتساب'}</span>{r.mode === 'ai' && <span className="badge bg-brand-50 text-brand-800">صياغة ذكاء اصطناعي</span>}
        <span className={`badge ${REM_STATUS[r.status][1]} ms-auto`}>{REM_STATUS[r.status][0]}</span></div>
      <div className="text-sm text-muted">المتبقي <b className="num text-ink">{omr(r.balance)}</b>{r.days_overdue > 0 && ` · متأخرة ${r.days_overdue} يوماً`}</div>
      <div className="font-semibold">{r.subject}</div>
      {edit ? <textarea className="input" rows="8" value={body} onChange={(e) => setBody(e.target.value)} /> : <pre className="whitespace-pre-wrap font-sans text-sm leading-7 bg-surface border border-line rounded-lg p-3 max-h-56 overflow-auto">{r.body}</pre>}
      {r.error && <p className="text-bad text-sm">⚠ {r.error}</p>}{err && <p role="alert" className="text-bad text-sm font-semibold">{err}</p>}
      {can && actionable && (
        <div className="flex flex-wrap gap-2">
          {edit ? <><button className="btn btn-primary" onClick={save}>حفظ التعديل</button><button className="btn btn-ghost" onClick={() => { setEdit(false); setBody(r.body) }}>إلغاء</button></> : <button className="btn btn-ghost" onClick={() => setEdit(true)}>تعديل النص</button>}
          {r.channel === 'email' && r.status !== 'approved' && <button className="btn btn-ghost" onClick={() => act('approve')}>اعتماد للإرسال</button>}
          {r.channel === 'email' && <button className="btn btn-primary" onClick={() => act('send')}><Icon name="mail" size={18} /> إرسال الآن</button>}
          {wa && <a className="btn btn-primary" href={wa} target="_blank" rel="noreferrer" onClick={() => act('mark_sent')}>فتح واتساب وتسجيل الإرسال</a>}
          <button className="btn btn-ghost" onClick={() => act('skip')}>تخطّي</button></div>)}
    </article>
  )
}

export default function Collections() {
  const user = useAuth()
  const can = canWrite(user)
  const [rem, setRem] = useState([])
  const [plans, setPlans] = useState([])
  const [tab, setTab] = useState('todo')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => { api('/reminders').then(setRem); api('/plans').then(setPlans) }
  useEffect(() => { load() }, [])
  const run = async () => { setBusy(true); try { const r = await api('/collections/run', { method: 'POST' }); setMsg(`وكيل التحصيل: ${r.reminders} تذكير جديد، ${r.plans_proposed} خطة تسوية مقترحة، ${r.defaulted} خطة متعثرة.`); load() } finally { setBusy(false) } }
  const plan = async (id, a) => { await api(`/plans/${id}/${a}`, { method: 'POST' }); load() }
  const todo = rem.filter((r) => ['draft', 'approved', 'failed'].includes(r.status))
  const done = rem.filter((r) => ['sent', 'skipped'].includes(r.status))
  const pp = plans.filter((p) => p.status === 'proposed')
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold flex-1">التحصيل والتذكيرات</h1>{can && <button className="btn btn-primary" disabled={busy} onClick={run}><Icon name="bot" size={18} />{busy ? 'جارٍ التشغيل…' : 'تشغيل وكيل التحصيل الآن'}</button>}</div>
      {msg && <p role="status" className="text-ok font-semibold">{msg}</p>}
      <div className="flex flex-wrap gap-2">{[['todo', `بانتظار الإرسال (${todo.length})`], ['plans', `خطط التسوية (${plans.length})`], ['done', `السجل (${done.length})`]].map(([k, l]) => <button key={k} className={`btn ${tab === k ? 'btn-primary' : 'btn-ghost'} !min-h-[40px]`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'todo' && (todo.length === 0 ? <p className="card text-muted">لا توجد تذكيرات بانتظارك. يولّد الوكيل التذكيرات يومياً 08:00 بتوقيت مسقط، أو شغّله الآن.</p> : todo.map((r) => <Reminder key={r.id} r={r} onChange={load} can={can} />))}
      {tab === 'done' && (done.length === 0 ? <p className="card text-muted">لا يوجد سجل بعد.</p> : done.map((r) => <Reminder key={r.id} r={r} onChange={load} can={false} />))}
      {tab === 'plans' && (plans.length === 0 ? <p className="card text-muted">لا توجد خطط. يقترح الوكيل خطة عندما تتأخر فاتورة 14 يوماً وتتجاوز 100 ر.ع.</p> : plans.map((p) => (
        <article key={p.id} className="card space-y-3">
          <div className="flex flex-wrap items-center gap-2"><Link to={`/invoices/${p.invoice_id}`} className="font-bold underline text-brand-800 num">{p.invoice}</Link><span>{p.customer}</span>
            <span className={`badge ms-auto ${{ proposed: 'bg-amber-100 text-amber-900', active: 'bg-sky-100 text-sky-900', completed: 'bg-emerald-100 text-emerald-900', defaulted: 'bg-red-100 text-red-900', rejected: 'bg-slate-200 text-slate-600' }[p.status]}`}>{{ proposed: 'مقترحة', active: 'سارية', completed: 'مكتملة', defaulted: 'متعثرة', rejected: 'مرفوضة' }[p.status]}</span></div>
          <p className="text-sm text-muted leading-7">{p.rationale}</p>
          <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">{p.installments.map((x) => <li key={x.n} className="border border-line rounded-lg p-3"><div className="text-xs text-muted">الدفعة {x.n} — {dateAr(x.due)}</div><b className="num">{omr(x.amount)}</b></li>)}</ol>
          {can && p.status === 'proposed' && <div className="flex gap-2"><button className="btn btn-primary" onClick={() => plan(p.id, 'accept')}>اعتماد الخطة</button><button className="btn btn-ghost" onClick={() => plan(p.id, 'reject')}>رفض</button></div>}
        </article>)))}
      {tab === 'plans' && pp.length > 0 && <p className="text-xs text-muted">اعتماد الخطة يوقف التذكيرات العادية للفاتورة ويراقب الوكيل التزام العميل بمواعيد الدفعات.</p>}
    </div>
  )
}
