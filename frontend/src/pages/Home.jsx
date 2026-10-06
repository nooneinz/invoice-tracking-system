import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../layout.jsx'

const fmt = (b) => (b / 1000).toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }
const iso = (d) => d.toISOString().slice(0, 10)

/* ===== المعاينة المباشرة للفاتورة: نفس منطق الحساب بالبيسة في الخادم ===== */
function LiveInvoice() {
  const [lines, setLines] = useState([{ d: 'خدمات صيانة سنوية', q: 2, p: 450 }, { d: 'ترخيص برنامج', q: 1, p: 120.5 }])
  const [days, setDays] = useState(30)
  const t = useMemo(() => {
    const sub = lines.reduce((s, l) => s + Math.round(Number(l.q || 0) * Math.round(Number(l.p || 0) * 1000)), 0)
    const vat = Math.round(sub * 0.05)
    return { sub, vat, total: sub + vat }
  }, [lines])
  const set = (i, k, v) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)))
  const today = new Date()
  return (
    <div className="sheet rise bg-white rounded-xl border border-line p-5 md:p-6 space-y-4 max-w-md w-full mx-auto" style={{ transform: 'rotate(-.6deg)' }}>
      <div className="flex justify-between items-start">
        <div><div className="font-display font-bold text-brand-800 text-lg">فاتورة ضريبية</div><div className="text-xs text-muted num">INV-2026-0042</div></div>
        <span className="badge bg-sky-100 text-sky-900">معاينة مباشرة</span>
      </div>
      <div className="text-sm"><span className="text-muted">العميل: </span><b>شركة الخليج للتجارة</b></div>
      <table className="w-full text-sm">
        <thead><tr className="text-muted text-xs"><th className="text-start font-semibold pb-1">البند</th><th className="font-semibold pb-1 w-14">الكمية</th><th className="font-semibold pb-1 w-24">السعر</th></tr></thead>
        <tbody>{lines.map((l, i) => (
          <tr key={i} className="border-t border-line"><td className="py-1.5">{l.d}</td>
            <td><input aria-label={`الكمية — ${l.d}`} className="input !min-h-[36px] !px-2 num text-center" type="number" min="0" step="1" value={l.q} onChange={(e) => set(i, 'q', e.target.value)} /></td>
            <td className="ps-2"><input aria-label={`سعر الوحدة — ${l.d}`} className="input !min-h-[36px] !px-2 num text-center" type="number" min="0" step="0.001" value={l.p} onChange={(e) => set(i, 'p', e.target.value)} /></td></tr>))}</tbody>
      </table>
      <dl className="text-sm space-y-1 border-t border-line pt-3">
        <div className="flex justify-between"><dt className="text-muted">المجموع قبل الضريبة</dt><dd className="num">{fmt(t.sub)}</dd></div>
        <div className="flex justify-between"><dt className="text-muted">ضريبة القيمة المضافة 5%</dt><dd className="num">{fmt(t.vat)}</dd></div>
        <div className="flex justify-between font-bold text-base text-brand-800"><dt>الإجمالي (ر.ع)</dt><dd className="num">{fmt(t.total)}</dd></div>
      </dl>
      <div className="flex items-center gap-3 text-sm bg-brand-50 rounded-lg px-3 py-2">
        <Icon name="clock" size={18} className="text-brand-800" />
        <label htmlFor="days" className="text-muted">الائتمان</label>
        <select id="days" className="input !min-h-[34px] !w-auto !py-0" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[15, 30, 45, 60].map((d) => <option key={d} value={d}>{d} يوماً</option>)}</select>
        <span className="ms-auto">يستحق <b className="num">{iso(addDays(today, days))}</b></span>
      </div>
    </div>
  )
}

const STAGES = [
  ['-3', 'قبل الاستحقاق', 'friendly', 'ودّية', 'تذكير ودّي: الفاتورة INV-2026-0042 تستحق في 2026-11-04', 'نود تذكيركم بأن الفاتورة رقم INV-2026-0042 بمبلغ 1,250.000 ر.ع تستحق السداد بتاريخ 2026-11-04، أي بعد 3 أيام. شاكرين لكم حسن تعاونكم.'],
  ['0', 'يوم الاستحقاق', 'friendly', 'ودّية', 'الفاتورة INV-2026-0042 تستحق اليوم', 'نفيدكم بأن الفاتورة رقم INV-2026-0042 بمبلغ 1,250.000 ر.ع تستحق السداد اليوم. نأمل إتمام السداد في أقرب وقت.'],
  ['+7', 'بعد 7 أيام', 'neutral', 'محايدة', 'تذكير: الفاتورة INV-2026-0042 متأخرة 7 أيام', 'تجاوزت الفاتورة تاريخ استحقاقها بمدة 7 أيام، والمتبقي 1,250.000 ر.ع. نأمل التكرم بإتمام السداد خلال الأيام القادمة.'],
  ['+14', 'بعد 14 يوماً', 'firm', 'حازمة', 'تذكير: الفاتورة INV-2026-0042 متأخرة 14 يوماً', 'نلفت عنايتكم إلى وجود فاتورتين متأخرتين بإجمالي 2,100.000 ر.ع، ونأمل السداد خلال 7 أيام حفاظاً على شروط الائتمان. ويقترح الوكيل خطة تسوية على 3 دفعات للمدير المالي.'],
  ['+30', 'بعد 30 يوماً', 'firm', 'حازمة', 'إشعار نهائي: الفاتورة INV-2026-0042 متأخرة 30 يوماً', 'رغم تذكيراتنا السابقة ما زالت الفاتورة غير مسددة. نأمل السداد خلال 7 أيام، ويسعدنا بحث خطة سداد على دفعات، وإلا اضطررنا لمراجعة شروط الائتمان.'],
]
const TONE_CLS = { friendly: 'bg-emerald-100 text-emerald-900', neutral: 'bg-sky-100 text-sky-900', firm: 'bg-red-100 text-red-900' }

const FAQ = [
  ['هل يرسل الوكيل رسائل دون علمي؟', 'لا. تُحفظ الرسائل مسودات تعتمدها أنت، إلا إن فعّلت الإرسال التلقائي للتذكيرات الودية قبل الاستحقاق فقط، وبعد ضبط SMTP.'],
  ['كيف يتعامل مع الدفعات الجزئية؟', 'تُسجَّل كل دفعة بمرجعها وتتحدّث حالة الفاتورة إلى «مدفوعة جزئياً»، ويُرفض أي مبلغ أكبر من المتبقي. وللمتأخرات الكبيرة يقترح الوكيل خطة تقسيط تعتمدها.'],
  ['هل تتصل بوابة الدفع؟', 'يوجد webhook موقّع بـ HMAC-SHA256 يستقبل إشعارات أي بوابة دفع ويمنع تكرار الدفعة بالمرجع. الربط المباشر مع Stripe غير مضمَّن حالياً.'],
  ['كيف أستورد كشف الحساب البنكي؟', 'ملف CSV بأعمدة التاريخ والمبلغ والوصف والمرجع واسم الجهة. تُتجاهل الخصومات وتُمنع الحركات المكررة.'],
]

export default function Home({ authed }) {
  const [stage, setStage] = useState(3)
  const st = STAGES[stage]
  const cta = authed ? '/' : '/login'
  return (
    <>
      {/* ===== Hero ===== */}
      <section className="ledger relative overflow-hidden border-b border-line">
        <div className="max-w-6xl mx-auto px-4 py-14 md:py-20 grid lg:grid-cols-[1.05fr_1fr] gap-12 items-center">
          <div className="space-y-6">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-brand-800 bg-brand-50 border border-brand-800/20 rounded-md px-3 py-1"><Icon name="coin" size={16} /> متابعة الفواتير والمدفوعات بين الشركات</p>
            <h1 className="font-display text-4xl md:text-5xl font-bold leading-[1.35]">حسابات مستحقة<br /><span className="text-brand-800">لا تنتظر التذكير اليدوي</span></h1>
            <p className="text-lg text-muted leading-9 max-w-xl">أصدر الفاتورة، وتابع الدفعات الجزئية، ودع الوكلاء يذكّرون العملاء بنبرة تناسب سجل كل واحد منهم، ويطابقون التحويلات البنكية ويغلقون المسدّد.</p>
            <div className="flex flex-wrap gap-3">
              <Link to={cta} className="btn btn-primary !min-h-[52px] px-7 text-base">{authed ? 'افتح لوحة التحصيل' : 'ادخل إلى حسابك'}</Link>
              <a href="#cycle" className="btn btn-ghost !min-h-[52px] px-6">شاهد دورة التحصيل</a>
            </div>
            <p className="text-sm text-muted flex items-center gap-2"><Icon name="shield" size={16} /> حساب بالبيسة بأعداد صحيحة — لا أخطاء فاصلة عائمة.</p>
          </div>
          <LiveInvoice />
        </div>
      </section>

      {/* ===== دورة التحصيل التفاعلية ===== */}
      <section id="cycle" className="max-w-6xl mx-auto px-4 py-20 scroll-mt-28">
        <div className="max-w-2xl mb-8"><h2 className="font-display text-3xl font-bold mb-2">وكيل التحصيل يعرف من يخاطب وكيف</h2>
          <p className="text-muted leading-8">كل مرحلة بنص مختلف، والنبرة تتغير حسب سجل العميل: من يسدد في موعده يصله تذكير ودّي، ومن تكرر تأخره يصله نص أحزم.</p></div>
        <div className="grid lg:grid-cols-[320px_1fr] gap-6">
          <div role="tablist" aria-label="مراحل التذكير" className="flex lg:flex-col gap-2 overflow-x-auto pb-1">
            {STAGES.map((s, i) => (
              <button key={s[0]} role="tab" aria-selected={i === stage} onClick={() => setStage(i)}
                className={`text-start rounded-xl border px-4 py-3 shrink-0 min-w-[150px] transition-colors ${i === stage ? 'bg-brand-800 text-white border-brand-800' : 'bg-white border-line hover:border-brand-700'}`}>
                <div className="text-xs opacity-80 num">{s[0] === '0' ? 'يوم الاستحقاق' : `${s[0]} يوم`}</div><div className="font-bold">{s[1]}</div>
              </button>))}
          </div>
          <article className="card space-y-3" role="tabpanel">
            <div className="flex flex-wrap items-center gap-2"><span className={`badge ${TONE_CLS[st[2]]}`}>نبرة {st[3]}</span><span className="text-xs text-muted">مثال على صياغة الوكيل — البريد أو واتساب</span></div>
            <h3 className="font-bold text-lg">{st[4]}</h3>
            <p className="leading-9 bg-surface rounded-lg p-4 border border-line">السادة / شركة الخليج للتجارة المحترمين،<br />{st[5]}</p>
            <p className="text-sm text-muted">تُحفظ مسودة لاعتمادك، وتُرفق الفاتورة PDF بالبريد، ويفتح زر واتساب الرسالة جاهزة.</p>
          </article>
        </div>
      </section>

      {/* ===== المطابقة البنكية ===== */}
      <section id="reconcile" className="bg-ink text-white scroll-mt-28 relative overflow-hidden">
        <div className="absolute inset-0 ledger-dark" aria-hidden="true" />
        <div className="relative max-w-6xl mx-auto px-4 py-20 grid lg:grid-cols-[1fr_1.2fr] gap-12 items-center">
          <div className="space-y-4">
            <h2 className="font-display text-3xl font-bold">ارفع كشف البنك، وانتهِ من المطابقة</h2>
            <p className="text-white/80 leading-8">وكيل المطابقة يقرأ رقم الفاتورة والمبلغ واسم الجهة، ويغلق ما كانت ثقته عالية، ويعرض لك سبب كل اقتراح للمراجعة. يدعم الدفعات الجزئية وتحويلاً واحداً يسدّد عدة فواتير.</p>
            <Link to={cta} className="btn bg-white text-brand-800 hover:bg-brand-50">جرّب الاستيراد</Link>
          </div>
          <div className="space-y-3" aria-label="أمثلة على قرارات وكيل المطابقة">
            {[['تحويل 1,050.000 — مرجع INV-2026-0031', 'رقم الفاتورة والمبلغ يطابقان', 98, 'أُغلقت تلقائياً', 'bg-emerald-400'],
              ['تحويل 315.000 — مؤسسة نزوى للتوريدات', 'اسم العميل يتطابق والمبلغ يساوي متبقي فاتورة واحدة', 88, 'مقترحة لتأكيدك', 'bg-amber-300'],
              ['إيداع 77.770 — جهة مجهولة', 'لا اسم ولا مبلغ مطابقان', 0, 'بلا مطابقة', 'bg-white/30']].map(([a, b, c, d, col]) => (
              <div key={a} className="rounded-xl bg-white/[0.07] border border-white/15 p-4">
                <div className="flex justify-between gap-3 flex-wrap"><b className="num text-sm">{a}</b><span className="text-sm font-semibold">{d}</span></div>
                <p className="text-sm text-white/70 mt-1">{b}</p>
                <div className="mt-2 h-1.5 rounded bg-white/10 overflow-hidden" role="img" aria-label={`الثقة ${c}%`}><div className={`h-full ${col}`} style={{ width: `${c}%` }} /></div>
              </div>))}
            <p className="text-xs text-white/60">أمثلة توضيحية لأنواع القرارات.</p>
          </div>
        </div>
      </section>

      {/* ===== دقة الحسابات ===== */}
      <section id="integrity" className="max-w-6xl mx-auto px-4 py-20 scroll-mt-28">
        <h2 className="font-display text-3xl font-bold mb-8">مبني لحسابات لا تخطئ</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 bg-white border border-line rounded-2xl divide-y sm:divide-y-0 sm:divide-x sm:divide-x-reverse divide-line overflow-hidden">
          {[['coin', 'أعداد صحيحة بالبيسة', 'كل مبلغ يُخزَّن بالبيسة (1 ر.ع = 1000 بيسة) فلا فروق كسرية في المجاميع.'], ['refresh', 'معاملات ACID', 'الدفعة وتحديث الفاتورة وإغلاقها تتم معاً أو لا تتم، مع قفل الصف على PostgreSQL.'], ['shield', 'سجل تدقيق متسلسل', 'تجزئة SHA-256 لكل حركة؛ أي تعديل على سجل قديم يُكتشف.'], ['check', 'Webhook موقّع', 'إشعارات الدفع بتوقيع HMAC-SHA256 ومرجع فريد يمنع تكرار الدفعة.']].map(([i, t, d]) => (
            <div key={t} className="p-6 space-y-2"><Icon name={i} size={26} className="text-brand-800" /><h3 className="font-bold">{t}</h3><p className="text-sm text-muted leading-7">{d}</p></div>))}
        </div>
      </section>

      <section id="faq" className="max-w-3xl mx-auto px-4 pb-20 scroll-mt-28">
        <h2 className="font-display text-3xl font-bold mb-6">أسئلة شائعة</h2>
        <div className="divide-y divide-line border-y border-line">{FAQ.map(([q, a]) => (
          <details key={q} className="group py-4"><summary className="cursor-pointer font-bold flex justify-between gap-4 items-center">{q}<span className="text-brand-800 text-2xl leading-none transition-transform group-open:rotate-45" aria-hidden="true">+</span></summary><p className="text-muted leading-8 mt-3">{a}</p></details>))}</div>
      </section>

      <section className="bg-brand-800 text-white">
        <div className="max-w-6xl mx-auto px-4 py-14 flex flex-wrap items-center justify-between gap-6">
          <div><h2 className="font-display text-3xl font-bold">ابدأ بإصدار أول فاتورة</h2><p className="text-white/80 mt-1">وتابعها حتى آخر بيسة.</p></div>
          <Link to={cta} className="btn bg-white text-brand-800 hover:bg-brand-50 !min-h-[52px] px-8">{authed ? 'لوحة التحصيل' : 'تسجيل الدخول'}</Link>
        </div>
      </section>
    </>
  )
}
