import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, omr, dateAr, canWrite } from '../api.js'
import { useAuth } from '../App.jsx'

const ST = { matched: ['مطابقة', 'bg-emerald-100 text-emerald-900'], suggested: ['اقتراح للمراجعة', 'bg-amber-100 text-amber-900'], unmatched: ['بلا مطابقة', 'bg-red-100 text-red-900'], ignored: ['متجاهَلة', 'bg-slate-200 text-slate-600'] }

export default function Bank() {
  const user = useAuth()
  const can = canWrite(user)
  const [rows, setRows] = useState([])
  const [filter, setFilter] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const load = () => api('/bank/transactions').then(setRows)
  useEffect(() => { load() }, [])
  const upload = async (e) => {
    const file = e.target.files[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file); setErr('')
    try { const r = await api('/bank/import', { method: 'POST', form: fd }); setMsg(`استُوردت ${r.imported} حركة: ${r.matched} طابقها الوكيل تلقائياً، ${r.suggested} مقترحة، ${r.unmatched} بلا مطابقة. مكرر ${r.duplicates}، خصومات متجاهَلة ${r.debits_skipped}، مرفوض ${r.rejected}.`); load() } catch (x) { setErr(x.message) }
    e.target.value = ''
  }
  const act = async (id, a) => { setErr(''); try { await api(`/bank/transactions/${id}/${a}`, { method: 'POST', body: {} }); load() } catch (x) { setErr(x.message) } }
  const rerun = async () => { const r = await api('/bank/reconcile', { method: 'POST' }); setMsg(r.detail); load() }
  const shown = rows.filter((t) => !filter || t.status === filter)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3"><h1 className="font-display text-2xl font-bold flex-1">المطابقة البنكية</h1>
        {can && <><button className="btn btn-ghost" onClick={rerun}>إعادة المطابقة</button><label className="btn btn-primary cursor-pointer">استيراد كشف الحساب (CSV)<input type="file" accept=".csv" className="sr-only" onChange={upload} /></label></>}</div>
      <p className="text-sm text-muted leading-7">أعمدة الملف: <code dir="ltr">date, amount, description, reference, counterparty</code> — تُستورد الإيداعات فقط، وتُتجاهل الحركات المكررة. يغلق الوكيل تلقائياً ما بلغت ثقته 90% فأكثر، ويعرض الباقي هنا بسبب كل اقتراح.</p>
      {msg && <p role="status" className="text-ok font-semibold">{msg}</p>}{err && <p role="alert" className="text-bad font-semibold">{err}</p>}
      <div className="flex flex-wrap gap-2">{[['', 'الكل'], ['suggested', 'اقتراحات'], ['unmatched', 'بلا مطابقة'], ['matched', 'مطابقة'], ['ignored', 'متجاهَلة']].map(([k, l]) => <button key={k} className={`btn ${filter === k ? 'btn-primary' : 'btn-ghost'} !min-h-[40px]`} onClick={() => setFilter(k)}>{l}</button>)}</div>
      <div className="space-y-3">
        {shown.length === 0 && <p className="card text-muted">لا توجد حركات. استورد كشف الحساب البنكي لتبدأ.</p>}
        {shown.map((t) => (
          <article key={t.id} className="card space-y-2">
            <div className="flex flex-wrap items-center gap-3"><b className="num text-lg">{omr(t.amount)}</b><span className="text-sm">{dateAr(t.date)}</span><span className="text-sm text-muted flex-1 min-w-[200px]">{t.counterparty} {t.description} {t.reference && <span className="num">· {t.reference}</span>}</span>
              <span className={`badge ${ST[t.status][1]}`}>{ST[t.status][0]}</span></div>
            {(t.reason || t.confidence > 0) && <div className="flex items-center gap-3 text-sm"><div className="w-28 h-1.5 rounded bg-slate-200 overflow-hidden" role="img" aria-label={`الثقة ${Math.round(t.confidence * 100)}%`}><div className={`h-full ${t.confidence >= 0.9 ? 'bg-emerald-600' : t.confidence >= 0.6 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${t.confidence * 100}%` }} /></div><span className="num text-muted">{Math.round(t.confidence * 100)}%</span><span>{t.reason}</span></div>}
            {t.suggestion.length > 0 && <ul className="text-sm space-y-1">{t.suggestion.map((s) => <li key={s.invoice_id}>← <Link className="underline text-brand-800 num" to={`/invoices/${s.invoice_id}`}>{s.invoice}</Link> ({s.customer}) بمبلغ <b className="num">{omr(s.amount)}</b> من متبقي {omr(s.invoice_balance)}</li>)}</ul>}
            {t.status === 'matched' && <p className="text-xs text-muted">طابقها: {t.matched_by}</p>}
            {can && ['suggested', 'unmatched'].includes(t.status) && <div className="flex gap-2">{t.suggestion.length > 0 && <button className="btn btn-primary" onClick={() => act(t.id, 'confirm')}>تأكيد المطابقة</button>}<button className="btn btn-ghost" onClick={() => act(t.id, 'ignore')}>تجاهل</button></div>}
          </article>))}
      </div>
    </div>
  )
}
