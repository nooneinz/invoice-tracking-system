import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

const P = {
  receipt: 'M4 2v20l3-2 3 2 3-2 3 2 3-2V2l-3 2-3-2-3 2-3-2zM8 8h8M8 12h8M8 16h5',
  bank: 'M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10M2 10l10-7 10 7',
  mail: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM22 6l-10 7L2 6',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  bot: 'M12 3v3M7 8h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-6a3 3 0 0 1 3-3zM9 13h.01M15 13h.01M9 17h6',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  shield: 'M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3zM9 12l2 2 4-4',
  check: 'M20 6L9 17l-5-5',
  refresh: 'M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M3 21v-5h5',
  clock: 'M12 6v6l4 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  home: 'M3 11l9-8 9 8M5 10v10h14V10',
  menu: 'M4 6h16M4 12h16M4 18h16',
  alert: 'M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  coin: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9 9.5c0-1 1-1.5 3-1.5s3 .5 3 1.5-1 1.2-3 1.5-3 .7-3 1.7 1 1.8 3 1.8 3-.8 3-1.8M12 6v2M12 16v2',
  send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
  github: 'M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  wallet: 'M3 7a2 2 0 0 1 2-2h13v4M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2zM16 14h.01',
}

export const Icon = ({ name, size = 20, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true"><path d={P[name]} /></svg>
)

export function Logo({ light = false, small = false }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width={small ? 30 : 36} height={small ? 30 : 36} viewBox="0 0 36 36" aria-hidden="true">
        <rect x="1" y="1" width="34" height="34" rx="9" fill={light ? '#fff' : '#7b1e2e'} />
        <path d="M10 12h16M10 18h16M10 24h9" stroke={light ? '#7b1e2e' : '#fff'} strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="26" cy="24" r="3.4" fill="none" stroke={light ? '#7b1e2e' : '#aeb6c2'} strokeWidth="2.2" />
      </svg>
      <span className="font-display font-bold text-xl leading-none">تحصيل</span>
    </span>
  )
}

export function PublicHeader() {
  const [open, setOpen] = useState(false)
  const items = [['#cycle', 'دورة التحصيل'], ['#reconcile', 'المطابقة البنكية'], ['#integrity', 'دقة الحسابات'], ['#faq', 'أسئلة']]
  return (
    <header className="bg-white border-b border-line sticky top-0 z-30">
      <div className="bg-brand-900 text-white/90 text-xs text-center py-1.5 px-3">الريال العماني بثلاث خانات عشرية · ضريبة القيمة المضافة 5% · بتوقيت مسقط</div>
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-6">
        <Link to="/" className="text-brand-800"><Logo /></Link>
        <nav className="hidden md:flex gap-1 flex-1" aria-label="الأقسام">{items.map(([h, l]) => <a key={h} href={h} className="px-3 py-2 rounded-lg text-sm font-semibold text-ink/80 hover:bg-brand-50 hover:text-brand-800">{l}</a>)}</nav>
        <Link to="/login" className="btn btn-primary ms-auto md:ms-0">تسجيل الدخول</Link>
        <button className="md:hidden btn btn-ghost !px-3" aria-label="القائمة" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="menu" /></button>
      </div>
      {open && <nav className="md:hidden border-t border-line px-4 py-2 flex flex-col" aria-label="الأقسام">{items.map(([h, l]) => <a key={h} href={h} onClick={() => setOpen(false)} className="py-3 border-b border-line last:border-0 font-semibold">{l}</a>)}</nav>}
    </header>
  )
}

export function Footer() {
  return (
    <footer className="bg-ink text-white/75 mt-auto border-t-4 border-brand-800">
      <div className="max-w-6xl mx-auto px-4 py-12 grid gap-8 md:grid-cols-4">
        <div className="md:col-span-2 space-y-3">
          <div className="text-white"><Logo light /></div>
          <p className="text-sm leading-8 max-w-md">لوحة مالية لمتابعة فواتير الشركات والدفعات الجزئية والذمم المتأخرة، بوكلاء يذكّرون ويطابقون. مصممة لحسابات سلطنة عُمان.</p>
        </div>
        <ul className="space-y-2 text-sm"><li className="text-white font-bold mb-1">المنتج</li><li><Link to="/about" className="hover:text-white">الصفحة التعريفية</Link></li><li><Link to="/" className="hover:text-white">لوحة التحكم</Link></li><li><Link to="/agents" className="hover:text-white">الوكلاء</Link></li></ul>
        <ul className="space-y-2 text-sm"><li className="text-white font-bold mb-1">تقني</li>
          <li><a className="hover:text-white inline-flex items-center gap-1" href="https://github.com/nooneinz/invoice-tracking-system" target="_blank" rel="noreferrer"><Icon name="github" size={16} /> الكود على GitHub</a></li><li>معاملات ACID · SHA-256 · HMAC</li></ul>
      </div>
      <div className="border-t border-white/10 text-center text-xs py-4">© {new Date().getFullYear()} تحصيل — B2B Invoice &amp; Payment Tracking · مسقط، سلطنة عُمان</div>
    </footer>
  )
}

const GROUPS = [
  ['المتابعة', [['/', 'لوحة التحكم', 'chart', true], ['/invoices', 'الفواتير', 'receipt'], ['/customers', 'العملاء', 'users']]],
  ['التحصيل', [['/collections', 'التذكيرات وخطط التسوية', 'mail'], ['/bank', 'المطابقة البنكية', 'bank'], ['/agents', 'الوكلاء', 'bot']]],
  ['النظام', [['/audit', 'سجل التدقيق', 'shield'], ['/admin', 'الإعدادات والمهام', 'gear']]],
]

export function Sidebar({ user, roleLabel, onLogout }) {
  const [open, setOpen] = useState(false)
  const link = ({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-colors ${isActive ? 'bg-brand-800 text-white' : 'text-ink/80 hover:bg-brand-50'}`
  return (
    <>
      <div className="lg:hidden sticky top-0 z-30 bg-white border-b border-line px-4 h-14 flex items-center justify-between">
        <Link to="/" className="text-brand-800"><Logo small /></Link>
        <button className="btn btn-ghost !px-3" aria-label="القائمة" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="menu" /></button>
      </div>
      <aside className={`${open ? 'block' : 'hidden'} lg:flex lg:flex-col bg-white border-e border-line lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen p-4 gap-5 overflow-y-auto`} aria-label="القائمة الرئيسية">
        <Link to="/" className="hidden lg:block text-brand-800 px-1 pt-1"><Logo /></Link>
        <nav className="flex-1 space-y-5">
          {GROUPS.map(([title, items]) => (
            <div key={title}><div className="text-xs font-bold text-muted px-3 mb-1">{title}</div>
              <div className="space-y-0.5">{items.map(([to, label, icon, end]) => <NavLink key={to} to={to} end={end} className={link} onClick={() => setOpen(false)}><Icon name={icon} size={18} />{label}</NavLink>)}</div></div>
          ))}
        </nav>
        <div className="border-t border-line pt-3 space-y-2">
          <div className="px-1"><div className="font-bold text-sm">{user.name}</div><div className="text-xs text-muted">{roleLabel}</div></div>
          <div className="flex gap-2"><Link to="/about" className="btn btn-ghost !min-h-[38px] flex-1 text-sm">عن النظام</Link>
            <button className="btn btn-ghost !min-h-[38px] flex-1 text-sm" onClick={onLogout}><Icon name="logout" size={16} />خروج</button></div>
        </div>
      </aside>
    </>
  )
}
