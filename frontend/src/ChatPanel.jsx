import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { Icon } from './layout.jsx'

function Trace({ trace }) {
  if (!trace?.length) return null
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer text-muted font-semibold">خطوات الوكيل ({trace.length} أداة)</summary>
      <ol className="mt-2 space-y-2">
        {trace.map((t, i) => (
          <li key={i} className="rounded-md bg-white border border-line p-2">
            <div className="font-semibold">⚙ {t.tool}</div>
            <div className="text-muted" dir="ltr">{JSON.stringify(t.input)}</div>
            <pre dir="auto" className="mt-1 whitespace-pre-wrap max-h-40 overflow-auto">{JSON.stringify(t.result, null, 1).slice(0, 1500)}</pre>
          </li>
        ))}
      </ol>
    </details>
  )
}

// لوحة محادثة مشتركة: agents = [{key,name,chips}]
export default function ChatPanel({ agents, aiEnabled, model }) {
  const [key, setKey] = useState(agents[0]?.key)
  const [threads, setThreads] = useState({})
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)
  const agent = agents.find((a) => a.key === key)
  const msgs = threads[key] || []
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [msgs.length, busy])

  const send = async (m) => {
    m = (m ?? text).trim()
    if (!m || busy) return
    setText('')
    const history = msgs.filter((x) => x.role).map((x) => ({ role: x.role, content: x.content }))
    setThreads((t) => ({ ...t, [key]: [...(t[key] || []), { role: 'user', content: m }] }))
    setBusy(true)
    try {
      const r = await api('/agents/chat', { method: 'POST', body: { agent: key, message: m, history } })
      setThreads((t) => ({ ...t, [key]: [...t[key], { role: 'assistant', content: r.reply, trace: r.trace, mode: r.mode }] }))
    } catch (e) {
      setThreads((t) => ({ ...t, [key]: [...t[key], { role: 'assistant', content: `⚠ ${e.message}` }] }))
    } finally { setBusy(false) }
  }

  return (
    <section className="card !p-0 overflow-hidden" aria-label="محادثة الوكيل">
      <div className="flex flex-wrap gap-2 p-3 border-b border-line bg-brand-50">
        {agents.map((a) => <button key={a.key} onClick={() => setKey(a.key)} className={`btn ${key === a.key ? 'btn-primary' : 'btn-ghost'}`}><Icon name="bot" size={18} /> {a.name}</button>)}
        <span className={`badge ms-auto self-center ${aiEnabled ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}>{aiEnabled ? `Claude — ${model}` : 'الوضع المحلي (بدون مفتاح)'}</span>
      </div>
      <div className="p-4 space-y-3 min-h-[320px] max-h-[460px] overflow-y-auto bg-surface" role="log" aria-live="polite">
        {msgs.length === 0 && (
          <div className="text-center text-muted py-8 space-y-3">
            <Icon name="bot" size={36} className="mx-auto text-brand-700" />
            <p>اسأل {agent.name} بالعربية. الأدوات للقراءة فقط، والقرار النهائي لك.</p>
            {!aiEnabled && <p className="text-xs">يفهم الأسئلة الشائعة محلياً. بإضافة مفتاح Claude يفهم أي صياغة ويربط عدة أدوات معاً.</p>}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 whitespace-pre-wrap leading-7 ${m.role === 'user' ? 'bg-brand-800 text-white' : 'bg-white border border-line'}`}>
              {m.content}
              {m.role === 'assistant' && <Trace trace={m.trace} />}
            </div>
          </div>
        ))}
        {busy && <div className="flex justify-end"><div className="rounded-2xl px-4 py-3 bg-white border border-line text-muted">الوكيل يفكر ويستدعي الأدوات…</div></div>}
        <div ref={end} />
      </div>
      <div className="p-3 border-t border-line space-y-2">
        <div className="flex flex-wrap gap-2">{agent.chips.map((c) => <button key={c} className="px-3 py-1.5 rounded-full border border-line bg-white text-sm hover:bg-brand-50" onClick={() => send(c)}>{c}</button>)}</div>
        <form onSubmit={(e) => { e.preventDefault(); send() }} className="flex gap-2">
          <label className="sr-only" htmlFor="chat-in">رسالتك</label>
          <input id="chat-in" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="اكتب سؤالك…" maxLength={1000} />
          <button className="btn btn-primary" disabled={busy || !text.trim()} aria-label="إرسال"><Icon name="send" size={18} className="-scale-x-100" /></button>
        </form>
      </div>
    </section>
  )
}
