import { useEffect, useRef, useState } from 'react'
import './index.css'
import logoUrl from './assets/logo.png'

function useTheme() {
  const getInitial = () => {
    try {
      const saved = localStorage.getItem('theme')
      if (saved) return saved === 'dark'
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return true
    } catch {}
    return true // default to dark
  }
  const [dark, setDark] = useState<boolean>(getInitial)
  useEffect(() => {
    const root = document.documentElement
    if (dark) root.classList.add('dark'); else root.classList.remove('dark')
    try { localStorage.setItem('theme', dark ? 'dark' : 'light') } catch {}
  }, [dark])
  return { dark, setDark }
}

function useRecorder() {
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null)
  const [recording, setRecording] = useState(false)
  const chunksRef = useRef<Blob[]>([])

  async function toggle() {
    if (!recorder) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      mr.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
      mr.onstop = () => setRecording(false)
      setRecorder(mr)
      mr.start(); setRecording(true)
      return
    }
    if (recorder.state === 'recording') {
      recorder.stop()
    } else {
      chunksRef.current = []
      recorder.start(); setRecording(true)
    }
  }

  function takeBlob() {
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    chunksRef.current = []
    return blob
  }

  return { toggle, takeBlob, recording }
}

function Message({ role, children }: { role: 'user' | 'ai', children: React.ReactNode }) {
  const isUser = role === 'user'
  return (
    <div className="w-full">
      <div className={`max-w-3xl mx-auto flex items-start gap-3 px-3 py-3 ${isUser ? 'justify-end' : ''}`}>
        {!isUser && (
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-white shadow-sm">AI</div>
        )}
        <div className={`${isUser ? 'bg-sky-500 text-white rounded-2xl rounded-tr-sm' : 'bg-white dark:bg-slate-800 dark:text-slate-100 text-slate-900 rounded-2xl rounded-tl-sm border border-slate-200 dark:border-slate-700'} shadow-sm px-4 py-3 max-w-[720px] leading-relaxed`}>{children}</div>
        {isUser && (
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-500 text-white shadow-sm">You</div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [client, setClient] = useState('')
  const [hours, setHours] = useState('')
  const [text, setText] = useState('')
  const [msgs, setMsgs] = useState<JSX.Element[]>([])
  const { toggle, takeBlob, recording } = useRecorder()
  const { dark, setDark } = useTheme()

  // Sidebar state
  const [attendee, setAttendee] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [quick, setQuick] = useState<'current'|'last'|null>(null)
  const [loadingCal, setLoadingCal] = useState(false)

  function onFrom(v: string){
    setFrom(v); if (v){ setQuick(null) }
  }
  function onTo(v: string){
    setTo(v); if (v){ setQuick(null) }
  }
  function selectQuick(q: 'current'|'last'){
    setQuick(q); setFrom(''); setTo('')
  }

  const rangeDisabled = quick !== null
  const quickDisabled = !!from || !!to
  const emailValid = !attendee || /.+@.+\..+/.test(attendee)
  const canFetch = emailValid && attendee && ((from && to) || quick !== null)

  async function fetchCalendar(){
    if (!canFetch) return
    setLoadingCal(true)
    try {
      // Placeholder: integrate real backend call later
      setMsgs(m=>[...m, <Message role="ai" key={m.length}>Fetched calendar data for <b>{attendee}</b> {quick? `(${quick} month)` : `(${from} → ${to})`}.</Message>])
    } finally { setLoadingCal(false) }
  }

  async function onMic() {
    await toggle()
    if (!recording) {
      return
    }
    setTimeout(async () => {
      const blob = takeBlob()
      setMsgs(m => [...m, <Message role="user" key={m.length}>[Voice note captured]</Message>])
      const fd = new FormData()
      fd.append('file', new File([blob], 'note.webm', { type: 'audio/webm' }))
      try {
        const res = await fetch('/stt', { method: 'POST', body: fd })
        const data = await res.json()
        setText(t => (t ? (t + '\n' + data.text) : data.text))
      } catch {
        setMsgs(m => [...m, <Message role="ai" key={m.length}>STT failed.</Message>])
      }
    }, 300)
  }

  async function onSend() {
    if (!text.trim()) return
    setMsgs(m => [...m, <Message role="user" key={m.length}>{text.split('\n').map((l,i)=><div key={i}>{l}</div>)}</Message>])
    setText('')
    setMsgs(m => [...m, <Message role="ai" key={m.length}><span className="inline-flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-slate-400"></span>Thinking…</span></Message>])
    try {
      const res = await fetch('/ai-invoice/allocate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client: client || null, total_hours: hours ? parseFloat(hours) : null, freeform: text }) })
      const data = await res.json()
      const rows = (data.line_items||[]).map((li: any, idx: number) => (
        <tr key={idx} className="border-b last:border-b-0 border-slate-200 dark:border-slate-700">
          <td className="py-2 pr-3">{li.subject}</td>
          <td className="py-2 pr-3 text-slate-600 dark:text-slate-300">{li.justification}</td>
          <td className="py-2 pl-3 text-right font-semibold">{Number(li.estimated_hours).toFixed(1)}</td>
        </tr>
      ))
      setMsgs(m => [...m, <Message role="ai" key={m.length}>
        <div className="text-sm text-slate-600 dark:text-slate-300 mb-3">
          <span className="font-medium text-slate-900 dark:text-slate-100">{data.client_name}</span>
          <span className="mx-2 text-slate-400">•</span>
          Total <span className="font-medium text-slate-900 dark:text-slate-100">{Number(data.total_hours_billed).toFixed(1)}h</span>
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-50/80 dark:bg-slate-900/40 text-slate-700 dark:text-slate-200">
              <tr>
                <th className="text-left py-2 px-3">Subject</th>
                <th className="text-left py-2 px-3">Justification</th>
                <th className="text-right py-2 px-3 w-24">Hours</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-800">{rows}</tbody>
          </table>
        </div>
      </Message>])
    } catch {
      setMsgs(m => [...m, <Message role="ai" key={m.length}>Allocation failed.</Message>])
    }
  }

  return (
    <div className="h-screen grid grid-rows-[auto,1fr] bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="px-4 py-3 bg-white/80 dark:bg-slate-900/80 backdrop-blur border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <img src={logoUrl} alt="Invoy" className="h-8 w-8 rounded-lg object-cover" />
          <div className="font-semibold text-slate-900 dark:text-slate-100 flex-1">Invoy • AI Assist</div>
          <button onClick={()=>setDark(!dark)} className="rounded-full px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 shadow-sm">{dark? 'Light' : 'Dark'}</button>
        </div>
      </header>
      {/* Two-column app area: sidebar + chat column */}
      {/* CHANGED: Increased gap to gap-8 and added some horizontal padding */}
      <div className="overflow-hidden p-4">
        <div className="flex gap-8 h-full w-full"> 
        {/* Sidebar */}
          {/* self-start sticky top-20 h-fit is good, but for full height, remove h-fit */}
          <aside className="w-[320px] bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm flex-shrink-0"> {/* Removed sticky/h-fit, added flex-shrink-0 for explicit sizing */}
            <div className="text-slate-900 dark:text-slate-100 font-semibold mb-3">Generate from Calendar</div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Attendee Email:</label>
            <input value={attendee} onChange={e=>setAttendee(e.target.value)} type="email" placeholder="name@company.com" className={`w-full mb-3 rounded-lg border px-3 py-2 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 ${emailValid? 'border-slate-300 dark:border-slate-700':'border-red-500'}`} />

            <div className="grid grid-cols-2 gap-2 mb-2">
              <div>
                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">From: Date</label>
                <input disabled={rangeDisabled} value={from} onChange={e=>onFrom(e.target.value)} type="date" className="w-full rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 disabled:opacity-50" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">To Date</label>
                <input disabled={rangeDisabled} value={to} onChange={e=>onTo(e.target.value)} type="date" className="w-full rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 disabled:opacity-50" />
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <button disabled={quickDisabled} onClick={()=>selectQuick('current')} className={`px-3 py-1.5 rounded-full border text-sm ${quick==='current' ? 'bg-sky-500 text-white border-sky-500' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-700'} disabled:opacity-50`}>Current Month</button>
              <button disabled={quickDisabled} onClick={()=>selectQuick('last')} className={`px-3 py-1.5 rounded-full border text-sm ${quick==='last' ? 'bg-sky-500 text-white border-sky-500' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-700'} disabled:opacity-50`}>Last Month</button>
            </div>

            <button onClick={fetchCalendar} disabled={!canFetch || loadingCal} className={`w-full rounded-lg px-4 py-2 font-semibold ${canFetch? 'bg-sky-500 hover:bg-sky-600 text-white':'bg-slate-200 text-slate-500'} ${loadingCal? 'opacity-75':''}`}>{loadingCal? 'Fetching…':'Fetch Calendar Data'}</button>
          </aside>

          {/* Right column: messages + composer */}
          {/* No changes needed here, flex-1 will handle remaining space */}
          <div className="flex-1 min-w-0 flex flex-col rounded-xl overflow-hidden bg-white/60 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800"> {/* Added some background and border to the main chat area */}
            <main className="flex-1 overflow-auto p-4 custom-scrollbar"> {/* Added custom-scrollbar for styling */}
              {msgs.length === 0 && (
                <div className="text-center text-slate-500 dark:text-slate-400 mt-8">
                  <div className="text-2xl font-semibold text-slate-800 dark:text-slate-100 mb-2">How can I help you invoice faster?</div>
                  <div>Describe your work or list subjects and total hours. Use the mic for voice.</div>
                </div>
              )}
              <div id="messages">
                {msgs}
              </div>
            </main>
            <div className="p-4 border-b border-slate-700/50 bg-slate-800/50">
              <div className="text-sm font-semibold text-slate-200 mb-2">
                  Invoice Generation Checklist 📝
              </div>
              <ul className="text-xs text-slate-400 list-disc list-inside space-y-1 pl-1">
                <li>
                    <strong>Client Name:</strong> Always mention the client you are billing (e.g., "for Acme Corp.").
                </li>
                <li>
                    <strong>Total Hours:</strong> State the <strong>exact total hours</strong> to be billed (e.g., "Bill for 40 hours total").
                </li>
                <li>
                    <strong>Work Subjects:</strong> List <strong>each distinct task</strong> or project area clearly (one per line is best).
                </li>
                <li>
                    <em>Example:</em> "10 hours for system setup. 3 hours for team training."
                </li>
            </ul>
            </div>
            {/* The footer is correctly positioned at the bottom of the right column */}
            <footer className="bg-white/90 dark:bg-slate-900/80 backdrop-blur border-t border-slate-200 dark:border-slate-800 p-3"> {/* Removed rounded-xl here as the parent is rounded */}
              <div className="grid gap-2">
                <div className="flex gap-2">
                  <input className="flex-1 rounded-full border border-slate-300 dark:border-slate-700 px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-300 dark:bg-slate-800 dark:text-slate-100" placeholder="Client (optional)" value={client} onChange={e=>setClient(e.target.value)} />
                  <input className="w-48 rounded-full border border-slate-300 dark:border-slate-700 px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-300 dark:bg-slate-800 dark:text-slate-100" placeholder="Total hours (optional)" value={hours} onChange={e=>setHours(e.target.value)} />
                </div>
                <div className="flex gap-2 items-end">
                  <textarea className="flex-1 rounded-2xl border border-slate-300 dark:border-slate-700 px-4 py-3 min-h-[110px] shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-300 dark:bg-slate-800 dark:text-slate-100" placeholder="Describe the work or list subjects (one per line)…" value={text} onChange={e=>setText(e.target.value)} />
                  <div className="flex flex-col gap-2">
                    <button onClick={onMic} className={`rounded-full px-5 py-2.5 text-white shadow ${recording? 'bg-red-600':'bg-slate-900 hover:bg-slate-800'}`}>{recording? 'Stop':'Mic'}</button>
                    <button onClick={onSend} className="rounded-full px-5 py-2.5 bg-sky-500 hover:bg-sky-600 text-white font-semibold shadow">Generate</button>
                  </div>
                </div>
              </div>
            </footer>
          </div>
        </div>
      </div>
    </div>
  )
}
