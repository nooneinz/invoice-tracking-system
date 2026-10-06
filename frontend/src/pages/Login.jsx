import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, setToken } from '../api.js'
import { Logo } from '../layout.jsx'

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { const r = await api('/auth/login', { method: 'POST', body: { email, password } }); setToken(r.token); onLogin(r.user); window.history.replaceState({}, '', '/') }
    catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex flex-col justify-between bg-brand-900 ledger-dark text-white p-12">
        <Link to="/" className="text-white"><Logo light /></Link>
        <div className="space-y-4 max-w-md">
          <h1 className="font-display text-4xl font-bold leading-[1.4]">كل ريال مستحق، تحت عينك</h1>
          <p className="text-white/80 leading-8">فواتير ودفعات جزئية وتنبيهات تأخر ومطابقة بنكية — في دفتر واحد بحساب دقيق بالبيسة.</p>
        </div>
        <p className="text-xs text-white/60">مسقط، سلطنة عُمان</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="card w-full max-w-sm space-y-5 !p-8">
          <Link to="/" className="lg:hidden text-brand-800 block"><Logo /></Link>
          <div><h2 className="font-display text-2xl font-bold">تسجيل الدخول</h2><p className="text-sm text-muted">ادخل إلى لوحة التحصيل.</p></div>
          <div><label className="lbl" htmlFor="email">البريد الإلكتروني</label><input id="email" className="input" type="email" dir="ltr" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div><label className="lbl" htmlFor="pw">كلمة المرور</label><input id="pw" className="input" type="password" dir="ltr" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          {err && <p role="alert" className="text-bad font-semibold">{err}</p>}
          <button className="btn btn-primary w-full !min-h-[48px]" disabled={busy}>{busy ? 'جارٍ الدخول…' : 'دخول'}</button>
          <Link to="/" className="block text-center text-sm text-brand-800 underline">العودة إلى الصفحة الرئيسية</Link>
        </form>
      </div>
    </div>
  )
}
