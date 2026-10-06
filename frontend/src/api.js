const KEY = 'tahseel_token'

export const getToken = () => localStorage.getItem(KEY)
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY))

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(`/api${path}`, { method, headers, body: payload })
  if (res.status === 401 && token) { setToken(null); window.location.href = '/login'; throw new Error('انتهت الجلسة') }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const d = data.detail
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('، ') : 'حدث خطأ')
  }
  return data
}

export async function openPdf(id) {
  const res = await fetch(`/api/invoices/${id}/pdf`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) throw new Error('تعذّر توليد الملف')
  window.open(URL.createObjectURL(await res.blob()), '_blank')
}

export const omr = (n) => `${Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} ر.ع`
export const omrShort = (n) => Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })
export const dateAr = (s) => (s ? new Date(s.length === 10 ? s + 'T00:00:00' : s).toLocaleDateString('ar-OM-u-nu-latn', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

export const INV_STATUS = {
  draft: ['مسودة', 'bg-slate-200 text-slate-700'], issued: ['صادرة', 'bg-sky-100 text-sky-900'], partial: ['مدفوعة جزئياً', 'bg-amber-100 text-amber-900'],
  overdue: ['متأخرة', 'bg-red-100 text-red-900'], paid: ['مسددة', 'bg-emerald-100 text-emerald-900'], void: ['ملغاة', 'bg-slate-200 text-slate-500'],
}
export const ROLE = { admin: 'مشرف النظام', finance: 'المحاسبة والتحصيل', viewer: 'اطلاع فقط' }
export const canWrite = (u) => ['admin', 'finance'].includes(u.role)
export const TONE = { friendly: ['ودّية', 'bg-emerald-100 text-emerald-900'], neutral: ['محايدة', 'bg-sky-100 text-sky-900'], firm: ['حازمة', 'bg-red-100 text-red-900'] }
export const STAGE = { 'd-3': 'قبل الاستحقاق', 'd+0': 'يوم الاستحقاق', 'd+7': 'بعد 7 أيام', 'd+14': 'بعد 14 يوماً', 'd+30': 'بعد 30 يوماً' }
export const REM_STATUS = { draft: ['بانتظار الاعتماد', 'bg-amber-100 text-amber-900'], approved: ['معتمد للإرسال', 'bg-sky-100 text-sky-900'], sent: ['أُرسل', 'bg-emerald-100 text-emerald-900'], failed: ['فشل', 'bg-red-100 text-red-900'], skipped: ['تم تخطيه', 'bg-slate-200 text-slate-600'] }
export const stageLabel = (s) => STAGE[s] || s
