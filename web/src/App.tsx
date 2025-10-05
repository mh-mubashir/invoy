import { useEffect, useRef, useState } from 'react'
import './index.css'

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
  return (
    <div className={`max-w-3xl mx-auto mb-3 rounded-2xl border ${role==='user' ? 'bg-sky-50 border-sky-100' : 'bg-white border-slate-200'} shadow-sm p-4`}> 
      {children}
    </div>
  )
}

export default function App() {
  const [client, setClient] = useState('')
  const [hours, setHours] = useState('')
  const [text, setText] = useState('')
  const [msgs, setMsgs] = useState<JSX.Element[]>([])
  const { toggle, takeBlob, recording } = useRecorder()

  async function onMic() {
    await toggle()
    if (!recording) {
      // just started
      return
    }
    // if it was recording and now stopped
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
    setMsgs(m => [...m, <Message role="ai" key={m.length}>Thinking…</Message>])
    try {
      const res = await fetch('/ai-invoice/allocate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client: client || null, total_hours: hours ? parseFloat(hours) : null, freeform: text }) })
      const data = await res.json()
      const rows = (data.line_items||[]).map((li: any, idx: number) => (
        <tr key={idx} className="border-b last:border-b-0">
          <td className="py-2 pr-3">{li.subject}</td>
          <td className="py-2 pr-3 text-slate-600">{li.justification}</td>
          <td className="py-2 pl-3 text-right font-semibold">{Number(li.estimated_hours).toFixed(1)}</td>
        </tr>
      ))
      setMsgs(m => [...m, <Message role="ai" key={m.length}>
        <div className="text-sm text-slate-600 mb-2">Client: <span className="font-medium text-slate-900">{data.client_name}</span> • Total: <span className="font-medium text-slate-900">{Number(data.total_hours_billed).toFixed(1)}h</span></div>
        <div className="overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-700">
              <tr><th className="text-left py-2 px-3">Subject</th><th className="text-left py-2 px-3">Justification</th><th className="text-right py-2 px-3 w-24">Hours</th></tr>
            </thead>
            <tbody className="bg-white">{rows}</tbody>
          </table>
        </div>
      </Message>])
    } catch {
      setMsgs(m => [...m, <Message role="ai" key={m.length}>Allocation failed.</Message>])
    }
  }

  return (
    <div className="h-screen grid grid-rows-[auto,1fr,auto] bg-slate-100">
      <header className="px-4 py-3 bg-slate-900 text-white shadow">
        <div className="max-w-5xl mx-auto flex items-center gap-2 font-semibold">Invoy • AI Assist</div>
      </header>
      <main className="overflow-auto p-4">
        <div id="messages" className="max-w-5xl mx-auto">
          {msgs}
        </div>
      </main>
      <footer className="bg-white border-t border-slate-200 p-3">
        <div className="max-w-5xl mx-auto grid gap-2">
          <div className="flex gap-2">
            <input className="flex-1 rounded-lg border border-slate-300 px-3 py-2" placeholder="Client (optional)" value={client} onChange={e=>setClient(e.target.value)} />
            <input className="w-48 rounded-lg border border-slate-300 px-3 py-2" placeholder="Total hours (optional)" value={hours} onChange={e=>setHours(e.target.value)} />
          </div>
          <div className="flex gap-2 items-start">
            <textarea className="flex-1 rounded-lg border border-slate-300 px-3 py-2 min-h-[100px]" placeholder="Describe the work or list subjects (one per line)…" value={text} onChange={e=>setText(e.target.value)} />
            <div className="flex flex-col gap-2">
              <button onClick={onMic} className={`rounded-lg px-4 py-2 text-white ${recording? 'bg-red-600':'bg-slate-900'}`}>{recording? 'Stop':'Mic'}</button>
              <button onClick={onSend} className="rounded-lg px-4 py-2 bg-sky-500 text-white font-semibold">Generate</button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
