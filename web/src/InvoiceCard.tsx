import { useState } from 'react'

interface InvoiceCardProps {
  data: any
  clientEmail: string
  onView: (path: string) => void
  onSend: (data: any, email: string) => void
}

export function InvoiceCard({ data, clientEmail, onView, onSend }: InvoiceCardProps) {
  const [viewed, setViewed] = useState(false)
  const [sent, setSent] = useState(false)

  const handleView = () => {
    setViewed(true)
    onView(data.path)
  }

  const handleSend = async () => {
    let email = clientEmail
    if (!email) {
      email = prompt('Enter client email to send invoice:') || ''
    }
    if (email) {
      await onSend(data, email)
      setSent(true)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 pb-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-lg">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
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
      <div className="grid grid-cols-2 gap-3">
        <button 
          onClick={handleView} 
          className="rounded-xl px-4 py-3 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-600 hover:to-blue-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          View
        </button>
        <button 
          onClick={handleSend}
          disabled={!viewed || sent}
          className={`rounded-xl px-4 py-3 font-semibold shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2 ${
            sent 
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white cursor-default'
              : viewed
                ? 'bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white'
                : 'bg-slate-300 dark:bg-slate-700 text-slate-500 dark:text-slate-600 cursor-not-allowed'
          }`}>
          {sent ? (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              Sent
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Send
            </>
          )}
        </button>
      </div>
    </div>
  )
}

