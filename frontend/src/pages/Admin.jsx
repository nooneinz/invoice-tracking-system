import { useEffect, useState } from 'react'
import { api, ROLE, dateAr } from '../api.js'
import { useAuth } from '../App.jsx'

const FIELDS = [['company_name', 'اسم شركتك (يظهر في الفاتورة)'], ['company_vatin', 'الرقم الضريبي'], ['company_address', 'العنوان'], ['company_phone', 'الهاتف'], ['company_email', 'البريد'], ['vat_rate', 'نسبة ضريبة القيمة المضافة (%)'], ['default_credit_days', 'مهلة السداد الافتراضية (يوم)'], ['dunning_offsets', 'مراحل التذكير (أيام نسبةً للاستحقاق)'], ['auto_threshold', 'حد الثقة للمطابقة التلقائية (0–1)']]

function Settings({ can }) {
  const [s, setS] = useState(null)
  const [msg, setMsg] = useState('')
  useEffect(() => { api('/settings').then(setS) }, [])
  if (!s) return null
  const save = async (e) => { e.preventDefault(); setS(await api('/settings', { method: 'PATCH', body: s })); setMsg('تم الحفظ.') }
  return (
    <form onSubmit={save} className="card grid md:grid-cols-2 gap-4">
      {FIELDS.map(([k, l]) => <div key={k}><label className="lbl" htmlFor={k}>{l}</label><input id={k} className="input" disabled={!can} value={s[k] ?? ''} onChange={(e) => setS({ ...s, [k]: e.target.value })} /></div>)}
      <div className="md:col-span-2"><label className="lbl" htmlFor="bd">بيانات الحساب البنكي (تظهر في الفاتورة والتذكيرات)</label><textarea id="bd" className="input" rows="3" disabled={!can} value={s.bank_details} onChange={(e) => setS({ ...s, bank_details: e.target.value })} placeholder={'بنك مسقط\nIBAN: OM..'} /></div>
      <label className="flex items-center gap-2"><input type="checkbox" disabled={!can} checked={s.auto_send === '1'} onChange={(e) => setS({ ...s, auto_send: e.target.checked ? '1' : '0' })} /> إرسال التذكيرات الودية تلقائياً (يتطلب SMTP)</label>
      <label className="flex items-center gap-2"><input type="checkbox" disabled={!can} checked={s.auto_reconcile === '1'} onChange={(e) => setS({ ...s, auto_reconcile: e.target.checked ? '1' : '0' })} /> إغلاق الفواتير تلقائياً عند الثقة العالية في المطابقة</label>
      {can && <button className="btn btn-primary md:col-span-2">حفظ الإعدادات</button>}{msg && <p role="status" className="text-ok font-semibold md:col-span-2">{msg}</p>}
    </form>
  )
}

function Jobs({ can }) {
  const [rows, setRows] = useState([])
  const [busy, setBusy] = useState('')
  const load = () => api('/jobs').then(setRows)
  useEffect(() => { load() }, [])
  const run = async (n) => { setBusy(n); try { await api(`/jobs/${n}/run`, { method: 'POST' }); await load() } finally { setBusy('') } }
  return (
    <div className="space-y-4">
      <div className="card !p-0 overflow-x-auto"><table className="w-full min-w-[700px]"><thead><tr><th className="th">المهمة</th><th className="th">الجدولة</th><th className="th">القادم</th><th className="th">آخر تشغيل</th><th className="th"></th></tr></thead>
        <tbody>{rows.map((j) => <tr key={j.name}><td className="td font-semibold">{j.title}</td><td className="td text-sm">{j.schedule}</td><td className="td text-sm">{j.next_run ? dateAr(j.next_run) : '—'}</td>
          <td className="td text-sm">{j.last ? <><span className={`badge ${j.last.status === 'success' ? 'bg-emerald-100 text-emerald-900' : 'bg-red-100 text-red-900'}`}>{j.last.status === 'success' ? 'نجح' : 'فشل'}</span> <span className="text-muted">{j.last.detail}</span></> : 'لم تعمل بعد'}</td>
          <td className="td">{can && <button className="btn btn-ghost !min-h-[38px]" disabled={busy === j.name} onClick={() => run(j.name)}>{busy === j.name ? 'جارٍ…' : 'تشغيل الآن'}</button>}</td></tr>)}</tbody></table></div>
      <section className="card text-sm leading-8"><h3 className="font-bold mb-1">ربط بوابة الدفع (Webhook)</h3>
        أرسل من بوابتك إلى <code dir="ltr">POST /api/webhooks/payments</code> الجسم <code dir="ltr">{'{"invoice_number","amount","reference"}'}</code> مع ترويسة <code dir="ltr">X-Signature</code> = HMAC-SHA256 للجسم بسرّ <code dir="ltr">WEBHOOK_SECRET</code>. يُمنع تكرار الدفعة بالمرجع، وتُرفض المبالغ الأكبر من المتبقي. الربط المباشر مع Stripe غير مضمَّن.</section>
    </div>
  )
}

function Users() {
  const [rows, setRows] = useState([])
  const [f, setF] = useState({ name: '', email: '', password: '', role: 'finance' })
  const [err, setErr] = useState('')
  const load = () => api('/users').then(setRows)
  useEffect(() => { load() }, [])
  const add = async (e) => { e.preventDefault(); setErr(''); try { await api('/users', { method: 'POST', body: f }); setF({ name: '', email: '', password: '', role: 'finance' }); load() } catch (x) { setErr(x.message) } }
  return (
    <div className="space-y-4">
      <form onSubmit={add} className="card grid md:grid-cols-5 gap-3 items-end">
        <div><label className="lbl" htmlFor="un">الاسم</label><input id="un" className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div><label className="lbl" htmlFor="ue">البريد</label><input id="ue" className="input" type="email" dir="ltr" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div><label className="lbl" htmlFor="up">كلمة المرور</label><input id="up" className="input" type="password" dir="ltr" minLength={8} required autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
        <div><label className="lbl" htmlFor="ur">الدور</label><select id="ur" className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{Object.entries(ROLE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <button className="btn btn-primary">إضافة مستخدم</button>{err && <p role="alert" className="text-bad md:col-span-5">{err}</p>}</form>
      <div className="card !p-0"><table className="w-full"><thead><tr><th className="th">الاسم</th><th className="th">البريد</th><th className="th">الدور</th><th className="th">الحالة</th><th className="th"></th></tr></thead>
        <tbody>{rows.map((u) => <tr key={u.id}><td className="td font-semibold">{u.name}</td><td className="td" dir="ltr">{u.email}</td><td className="td">{u.role_label}</td><td className="td">{u.active ? 'فعّال' : 'معطّل'}</td>
          <td className="td"><button className="btn btn-ghost !min-h-[38px]" onClick={async () => { try { await api(`/users/${u.id}`, { method: 'PATCH', body: { active: !u.active } }); load() } catch (x) { setErr(x.message) } }}>{u.active ? 'تعطيل' : 'تفعيل'}</button></td></tr>)}</tbody></table></div>
    </div>
  )
}

export default function Admin() {
  const user = useAuth()
  const can = ['admin', 'finance'].includes(user.role)
  const tabs = [['set', 'الإعدادات'], ['job', 'المهام والـ Webhook'], ...(user.role === 'admin' ? [['usr', 'المستخدمون']] : [])]
  const [tab, setTab] = useState('set')
  return (
    <div className="space-y-4"><h1 className="font-display text-2xl font-bold">الإعدادات والمهام</h1>
      <div className="flex gap-2 flex-wrap">{tabs.map(([k, l]) => <button key={k} className={`btn ${tab === k ? 'btn-primary' : 'btn-ghost'} !min-h-[40px]`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'set' && <Settings can={can} />}{tab === 'job' && <Jobs can={can} />}{tab === 'usr' && <Users />}</div>
  )
}
