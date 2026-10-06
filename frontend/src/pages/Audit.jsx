import { useEffect, useState } from 'react'
import { api, dateAr } from '../api.js'

export default function Audit() {
  const [logs, setLogs] = useState([])
  const [chain, setChain] = useState(null)
  useEffect(() => { api('/audit/logs').then(setLogs); api('/audit/verify').then(setChain) }, [])
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-bold">سجل التدقيق</h1>
      {chain && <p className={`card font-semibold ${chain.valid ? 'text-ok' : 'text-bad'}`}>{chain.valid ? `سلامة السجل: ✓ تم التحقق من ${chain.checked} حركة — لا يوجد أي تعديل غير مصرّح به.` : `⚠ تم اكتشاف تلاعب في السجل عند الحركة رقم ${chain.broken_at}`}</p>}
      <div className="card !p-0 overflow-x-auto"><table className="w-full min-w-[640px]">
        <thead><tr><th className="th">الوقت</th><th className="th">المنفّذ</th><th className="th">الإجراء</th><th className="th">التفاصيل</th></tr></thead>
        <tbody>{logs.map((l) => <tr key={l.id}><td className="td text-sm whitespace-nowrap">{dateAr(l.ts)}</td><td className="td">{l.user}</td><td className="td font-mono text-xs" dir="ltr">{l.action}</td><td className="td text-sm">{l.details}</td></tr>)}</tbody></table></div>
    </div>
  )
}
