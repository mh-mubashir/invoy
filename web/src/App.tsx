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
          <img src={logoUrl} alt="Invoy" className="h-9 w-9 rounded-xl object-cover shadow-sm flex-shrink-0" />
        )}
        <div className={`${isUser ? 'bg-sky-500 text-white rounded-2xl rounded-tr-sm' : 'bg-white dark:bg-slate-800 dark:text-slate-100 text-slate-900 rounded-2xl rounded-tl-sm border border-slate-200 dark:border-slate-700'} shadow-sm px-4 py-3 max-w-[720px] leading-relaxed max-h-[500px] overflow-y-auto`}>{children}</div>
        {isUser && (
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-500 text-white shadow-sm flex-shrink-0">You</div>
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
  const [invSummary, setInvSummary] = useState<{ path?: string; totalHours?: number; totalCost?: number; period?: string } | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

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
      // Placeholder for actual backend call.
      const periodLabel = quick === 'current' ? 'Current Month' : quick === 'last' ? 'Last Month' : `${from} → ${to}`
      const totalH = 12.5 // replace with real computed value from backend
      const hourly = 200 // could be read from config later
      const totalC = totalH * hourly
      const samplePath = '/invoices/INV-jane-doe_acme-com-202509.html' // placeholder for generated invoice
      setInvSummary({ path: samplePath, totalHours: totalH, totalCost: totalC, period: periodLabel })
      setPreviewUrl(samplePath)
      setMsgs(m=>[...m, <Message role="ai" key={m.length}>Fetched calendar data for <b>{attendee}</b> <span className="text-slate-500">({periodLabel})</span>.</Message>])
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

  async function finalizeInvoice(allocData: any) {
    try {
      const res = await fetch('/ai-invoice/finalize', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          client: allocData.client_name, 
          line_items: allocData.line_items, 
          billing_period: allocData.billing_period 
        }) 
      })
      const data = await res.json()
      setMsgs(m => [...m, <Message role="ai" key={Date.now()}>
        <div className="space-y-4">
          <div className="flex items-center gap-3 pb-3 border-b border-slate-200 dark:border-slate-700">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-lg">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
            </div>
            <div>
              <div className="font-semibold text-slate-900 dark:text-slate-100 text-base">Invoice Generated</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">Ready for preview and delivery</div>
            </div>
          </div>
          <div className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-2.5 text-sm">
            <div className="text-slate-500 dark:text-slate-400">Client</div>
            <div className="text-slate-900 dark:text-slate-100 font-medium">{data.client_name}</div>
            <div className="text-slate-500 dark:text-slate-400">Period</div>
            <div className="text-slate-900 dark:text-slate-100 font-medium">{data.billing_period}</div>
            <div className="text-slate-500 dark:text-slate-400">Hours</div>
            <div className="text-slate-900 dark:text-slate-100 font-medium">{data.total_hours.toFixed(1)}</div>
            <div className="text-slate-500 dark:text-slate-400">Amount</div>
            <div className="text-slate-900 dark:text-slate-100 font-semibold text-base">${data.total_cost.toFixed(2)}</div>
            <div className="text-slate-500 dark:text-slate-400">Invoice ID</div>
            <div className="text-slate-700 dark:text-slate-300 font-mono text-xs">{data.invoice_id}</div>
          </div>
          <button onClick={()=>setPreviewUrl(data.path)} className="w-full rounded-xl px-4 py-3 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-600 hover:to-blue-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
            View Invoice
          </button>
        </div>
      </Message>])
    } catch {
      setMsgs(m => [...m, <Message role="ai" key={Date.now()}>Failed to finalize invoice.</Message>])
    }
  }

  async function onSend() {
    if (!text.trim()) return
    setMsgs(m => [...m, <Message role="user" key={m.length}>{text.split('\n').map((l,i)=><div key={i}>{l}</div>)}</Message>])
    const inputText = text
    const inputClient = client
    const inputHours = hours
    setText('')
    setClient('')
    setHours('')
    const loaderId = Date.now()
    setMsgs(m => [...m, <Message role="ai" key={loaderId}>
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          <span className="h-2 w-2 rounded-full bg-sky-500 animate-bounce" style={{animationDelay:'0ms'}}></span>
          <span className="h-2 w-2 rounded-full bg-sky-500 animate-bounce" style={{animationDelay:'150ms'}}></span>
          <span className="h-2 w-2 rounded-full bg-sky-500 animate-bounce" style={{animationDelay:'300ms'}}></span>
        </div>
        <span className="text-slate-600 dark:text-slate-400 text-sm">Analyzing your request...</span>
      </div>
    </Message>])
    try {
      const res = await fetch('/ai-invoice/allocate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client: inputClient || null, total_hours: inputHours ? parseFloat(inputHours) : null, freeform: inputText }) })
      const data = await res.json()
      
      const rows = (data.line_items||[]).map((li: any, idx: number) => (
        <tr key={idx} className="border-b last:border-b-0 border-slate-200 dark:border-slate-700">
          <td className="py-2 pr-3">{li.subject || '-'}</td>
          <td className="py-2 pr-3 text-slate-600 dark:text-slate-300">{li.justification || '-'}</td>
          <td className="py-2 pl-3 text-right font-semibold">{(li.estimated_hours || 0).toFixed(1)}</td>
        </tr>
      ))
      // Remove loader and add response in one update
      setMsgs(m => [...m.filter((msg: any) => msg.key !== loaderId), <Message role="ai" key={Date.now()}>
        <div className="space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-700">
            <div>
              <div className="font-semibold text-slate-900 dark:text-slate-100">{data.client_name || 'Unknown Client'}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Total: {(data.total_hours_billed || 0).toFixed(1)}h • Confidence: {((data.confidence || 0) * 100).toFixed(0)}%</div>
            </div>
          </div>
          <div className="max-h-[280px] overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-700 dark:text-slate-200 sticky top-0">
                <tr>
                  <th className="text-left py-2.5 px-3 font-medium">Subject</th>
                  <th className="text-left py-2.5 px-3 font-medium">Justification</th>
                  <th className="text-right py-2.5 px-3 font-medium w-20">Hours</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800">{rows}</tbody>
            </table>
          </div>
          <button onClick={()=>finalizeInvoice(data)} className="w-full rounded-xl px-4 py-3 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all">
            Finalize & Generate Invoice
          </button>
        </div>
      </Message>])
    } catch (err) {
      setMsgs(m => [...m.filter((msg: any) => msg.key !== loaderId), <Message role="ai" key={Date.now()}>Allocation failed. Please try again.</Message>])
    }
  }

  return (
    <div className="h-screen grid grid-rows-[auto,1fr] bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="px-6 py-4 bg-white/70 dark:bg-slate-950/70 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-800/50">
        <div className="max-w-7xl mx-auto flex items-center gap-4">
          <img src={logoUrl} alt="Invoy AI" className="h-9 w-9 rounded-xl object-cover" />
          <div className="font-semibold text-[17px] tracking-tight text-slate-900 dark:text-white flex-1">Invoy AI</div>
          <button onClick={()=>setDark(!dark)} className="rounded-full px-4 py-1.5 text-[13px] font-medium border border-slate-300/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 bg-white/80 dark:bg-slate-800/80 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors backdrop-blur">
            {dark? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>
      {/* Two-column app area: sidebar + chat column */}
      {/* CHANGED: Increased gap to gap-8 and added some horizontal padding */}
      <div className="overflow-hidden p-4">
        <div className="flex gap-8 h-full w-full"> 
        {/* Sidebar */}
          {/* self-start sticky top-20 h-fit is good, but for full height, remove h-fit */}
          <aside className="w-[360px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-lg flex-shrink-0 overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
              <div className="text-slate-900 dark:text-slate-100 font-semibold text-lg">Generate from Calendar</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">Fetch billable meetings from your calendar</div>
            </div>

            <div className="px-6 py-5 space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Client Email</label>
                <input value={attendee} onChange={e=>setAttendee(e.target.value)} type="email" placeholder="name@company.com" className={`w-full rounded-lg border px-4 py-2.5 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 ${emailValid? 'border-slate-300 dark:border-slate-700':'border-red-500'}`} />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Date Range</label>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">From</div>
                    <input disabled={rangeDisabled} value={from} onChange={e=>onFrom(e.target.value)} type="date" className="w-full rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2.5 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 disabled:opacity-40 transition-opacity focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">To</div>
                    <input disabled={rangeDisabled} value={to} onChange={e=>onTo(e.target.value)} type="date" className="w-full rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2.5 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 disabled:opacity-40 transition-opacity focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Quick Select</label>
                <div className="flex items-center gap-2">
                  <button disabled={quickDisabled} onClick={()=>selectQuick('current')} className={`flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${quick==='current' ? 'bg-sky-500 text-white border-sky-500 shadow-sm' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-700 hover:border-sky-400'} disabled:opacity-40 disabled:cursor-not-allowed`}>Current Month</button>
                  <button disabled={quickDisabled} onClick={()=>selectQuick('last')} className={`flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${quick==='last' ? 'bg-sky-500 text-white border-sky-500 shadow-sm' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-700 hover:border-sky-400'} disabled:opacity-40 disabled:cursor-not-allowed`}>Last Month</button>
                </div>
              </div>

              <button onClick={fetchCalendar} disabled={!canFetch || loadingCal} className={`w-full rounded-lg px-4 py-3 font-semibold transition-all ${canFetch? 'bg-sky-500 hover:bg-sky-600 text-white shadow-md hover:shadow-lg':'bg-slate-200 dark:bg-slate-800 text-slate-500 dark:text-slate-600 cursor-not-allowed'} ${loadingCal? 'opacity-75':''}`}>{loadingCal? 'Fetching…':'Fetch Calendar Data'}</button>

              {invSummary && (
                <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 p-4 space-y-3 shadow-sm">
                  <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <span className="text-emerald-500">✓</span> Invoice Summary
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-600 dark:text-slate-400">Period</span>
                      <span className="text-slate-900 dark:text-slate-100 font-medium">{invSummary.period || '-'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600 dark:text-slate-400">Total Hours</span>
                      <span className="text-slate-900 dark:text-slate-100 font-medium">{invSummary.totalHours?.toFixed(2) ?? '-'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600 dark:text-slate-400">Total Cost</span>
                      <span className="text-slate-900 dark:text-slate-100 font-medium">{invSummary.totalCost ? `$${invSummary.totalCost.toFixed(2)}` : '-'}</span>
                    </div>
                  </div>
                  <button onClick={()=>{ if(invSummary.path){ setPreviewUrl(invSummary.path); window.scrollTo({top:0, behavior:'smooth'}); } }} disabled={!invSummary.path} className={`w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-all ${invSummary.path? 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-md hover:shadow-lg':'bg-slate-200 dark:bg-slate-800 text-slate-500 dark:text-slate-600 cursor-not-allowed'}`}>
                    {invSummary.path? '👁️ Preview Invoice' : 'Invoice will be generated'}
                  </button>
                </div>
              )}
            </div>
          </aside>

          {/* Center: chat column */}
          <div className="flex-1 min-w-0 flex flex-col rounded-xl overflow-hidden bg-white/60 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <main className="flex-1 overflow-y-auto p-4" style={{scrollBehavior:'smooth'}}>
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
            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-gradient-to-br from-sky-50 to-blue-50 dark:from-slate-800 dark:to-slate-900">
              <div className="flex items-start gap-3 mb-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-sky-500 flex items-center justify-center text-white font-bold text-sm">📝</div>
                <div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">Invoice Generation Checklist</div>
                  <div className="text-xs text-slate-600 dark:text-slate-400">Follow these guidelines for best results</div>
                </div>
              </div>
              <div className="space-y-2.5 text-xs text-slate-700 dark:text-slate-300">
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-sky-100 dark:bg-sky-900/40 flex items-center justify-center text-sky-600 dark:text-sky-400 font-bold text-[10px]">1</span>
                  <div><strong className="text-slate-900 dark:text-slate-100">Client Name:</strong> Always mention the client (e.g., "for Acme Corp.")</div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-sky-100 dark:bg-sky-900/40 flex items-center justify-center text-sky-600 dark:text-sky-400 font-bold text-[10px]">2</span>
                  <div><strong className="text-slate-900 dark:text-slate-100">Total Hours:</strong> State exact total (e.g., "Bill for 40 hours total")</div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-sky-100 dark:bg-sky-900/40 flex items-center justify-center text-sky-600 dark:text-sky-400 font-bold text-[10px]">3</span>
                  <div><strong className="text-slate-900 dark:text-slate-100">Work Subjects:</strong> List each distinct task (one per line is best)</div>
                </div>
              </div>
            </div>
            {/* Composer footer */}
            <footer className="bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 px-6 py-4">
              <div className="space-y-3">
                <div className="flex gap-3">
                  <input className="flex-1 rounded-xl border border-slate-300 dark:border-slate-700 px-4 py-2.5 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400" placeholder="Client Email" value={client} onChange={e=>setClient(e.target.value)} />
                </div>
                <div className="flex gap-3 items-end">
                  <textarea className="flex-1 rounded-xl border border-slate-300 dark:border-slate-700 px-4 py-3 min-h-[100px] resize-none bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400" placeholder="Describe the work or list subjects (one per line)…" value={text} onChange={e=>setText(e.target.value)} />
                  <div className="flex flex-col gap-2">
                    <button onClick={onMic} className={`rounded-xl px-5 py-2.5 font-medium text-white shadow-md transition-all ${recording? 'bg-red-500 hover:bg-red-600':'bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600'}`}>
                      {recording? '⏹️ Stop':'🎙️ Mic'}
                    </button>
                    <button onClick={onSend} className="rounded-xl px-5 py-2.5 bg-sky-500 hover:bg-sky-600 text-white font-semibold shadow-md hover:shadow-lg transition-all">
                      Generate
                    </button>
                  </div>
                </div>
              </div>
            </footer>
          </div>

          {/* Right: invoice preview panel */}
          <aside className="w-[540px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-lg flex-shrink-0 overflow-hidden flex flex-col">
            <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800">
              <div className="text-slate-900 dark:text-slate-100 font-semibold text-lg">Invoice Preview</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">Live preview of generated invoice</div>
            </div>
            <div className="flex-1 overflow-hidden">
              {previewUrl ? (
                <iframe src={previewUrl} className="w-full h-full border-0" title="Invoice Preview" />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400 dark:text-slate-600 text-sm px-6 text-center">
                  No invoice to preview yet. Generate one from calendar or AI assist.
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
