import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiCall } from '../../lib/api'
import { Button } from '../ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { StatusBadge } from './StatusBadge'
import { Phone, Smartphone, PhoneCall, Settings, Wrench, Loader2, FileDown, Clock } from 'lucide-react'

// Types for request status endpoint
interface AttemptRow {
  service_key: 'ringcentral'|'convoso'|'ytel'|'logics'|'genesys'
  status: 'pending'|'in_progress'|'success'|'failed'|'skipped'
  http_status?: number
  provider_request_id?: string
  started_at?: string
  finished_at?: string | null
  duration_seconds?: number
  error_message?: string | null
  attempt_no?: number
  response_payload?: any
}

interface StatusResponse {
  aggregate?: any
  attempts: AttemptRow[]
  attempt_totals?: Record<string, number>
}

interface EventRow {
  occurred_at: string
  level: string
  component: string
  action: string
  details: any
}

export const RequestDetailsModal: React.FC<{ requestId: number; onClose: ()=>void }>
  = ({ requestId, onClose }) => {
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string|undefined>()
  const [status, setStatus] = useState<StatusResponse>({ attempts: [] })
  const [events, setEvents] = useState<EventRow[]>([])
  const [retrying, setRetrying] = useState<Record<string, boolean>>({})

  const phone = useMemo(() => status.aggregate?.phone_e164 || status.aggregate?.phone || '', [status])
  const requester = useMemo(() => status.aggregate?.requested_by_name || status.aggregate?.requested_by || '', [status])
  const reviewer = useMemo(() => status.aggregate?.reviewed_by_name || status.aggregate?.approved_by || '', [status])

  const load = async () => {
    setLoading(true)
    setErr(undefined)
    try {
      const [s, e] = await Promise.all([
        apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${requestId}/status`),
        apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${requestId}/events`),
      ])
      setStatus(s)
      setEvents(e.events || [])
    } catch (e: any) {
      setErr(e?.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId])

  const fmtDur = (s?: number|null) => {
    if (s == null) return ''
    return `${s.toFixed(1)}s`
  }

  const fmtPhone = (p: string) => {
    if (!p) return ''
    const d = p.replace(/\D/g, '')
    if (d.length === 11 && d.startsWith('1')) {
      return `+1-${d.slice(1,4)}-${d.slice(4,7)}-${d.slice(7)}`
    }
    if (d.length === 10) return `${d.slice(0,3)}-${d.slice(3,6)}-${d.slice(6)}`
    return p
  }

  const iconFor = (key: string) => {
    switch (key) {
      case 'ringcentral': return <Phone className="w-4 h-4" />
      case 'convoso': return <Smartphone className="w-4 h-4" />
      case 'ytel': return <PhoneCall className="w-4 h-4" />
      case 'logics': return <Settings className="w-4 h-4" />
      case 'genesys': return <Wrench className="w-4 h-4" />
      default: return <Phone className="w-4 h-4" />
    }
  }

  const retry = async (service: string) => {
    setRetrying(prev => ({ ...prev, [service]: true }))
    try {
      await apiCall(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId, service_key: service, phone_e164: phone })
      })
      await load()
    } catch {
      // swallow; UI shows spinner/refresh
    } finally {
      setRetrying(prev => ({ ...prev, [service]: false }))
    }
  }

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ status, events }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dnc_request_${requestId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const attemptsByService = useMemo(() => {
    const map: Record<string, AttemptRow> = {}
    for (const a of status.attempts || []) map[a.service_key] = a
    return map
  }, [status])

  const totalDuration = useMemo(() => {
    const s = status.aggregate?.submitted_at || status.aggregate?.created_at
    const c = status.aggregate?.completed_at || status.aggregate?.decided_at
    if (!s || !c) return ''
    const ms = new Date(c).getTime() - new Date(s).getTime()
    if (ms < 0) return ''
    return `${(ms/1000).toFixed(1)}s`
  }, [status])

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" aria-modal="true" role="dialog">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-10 border-b p-4 bg-white flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-500">Request #{requestId}</div>
            <div className="text-xl font-semibold">{fmtPhone(phone)}</div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={(status.aggregate?.status || 'pending') as any} />
            <Button variant="outline" onClick={exportJson}><FileDown className="w-4 h-4 mr-1" />Export</Button>
            <Button variant="outline" onClick={load} disabled={loading}><Loader2 className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />Refresh</Button>
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-4 overflow-auto">
          {err && <div className="text-red-600 text-sm mb-2">{err}</div>}
          {loading ? (
            <div className="flex items-center gap-2 text-gray-600"><Loader2 className="w-4 h-4 animate-spin" /> Loading details…</div>
          ) : (
            <div className="space-y-4">
              {/* Meta section */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Card>
                  <CardHeader><CardTitle className="text-sm">Submitted</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <div>{status.aggregate?.submitted_at ? new Date(status.aggregate.submitted_at).toLocaleString() : '—'}</div>
                    <div className="text-gray-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Total: {totalDuration || '—'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-sm">Requested By</CardTitle></CardHeader>
                  <CardContent className="text-sm">{requester || '—'}</CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-sm">Approved By</CardTitle></CardHeader>
                  <CardContent className="text-sm">{reviewer || '—'}</CardContent>
                </Card>
              </div>

              {/* Request details */}
              <Card>
                <CardHeader><CardTitle>Request Details</CardTitle></CardHeader>
                <CardContent className="text-sm grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div><span className="text-gray-500">Reason:</span> {status.aggregate?.reason || '—'}</div>
                  <div><span className="text-gray-500">Channel:</span> {status.aggregate?.channel || '—'}</div>
                  <div className="md:col-span-2"><span className="text-gray-500">User Notes:</span> {status.aggregate?.notes || '—'}</div>
                  <div className="md:col-span-2"><span className="text-gray-500">Decision Notes:</span> {status.aggregate?.decision_notes || '—'}</div>
                </CardContent>
              </Card>

              {/* Systems */}
              <Card>
                <CardHeader><CardTitle>System Propagation</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {(['ringcentral','convoso','ytel','logics','genesys'] as const).map((key) => {
                    const a = attemptsByService[key]
                    const total = status.attempt_totals?.[key] || (a?.attempt_no || 1)
                    const dur = a?.duration_seconds
                    return (
                      <div key={key} className="flex items-start justify-between border p-2 rounded">
                        <div className="flex items-center gap-2">
                          {iconFor(key)}
                          <div className="font-medium capitalize">{key}</div>
                          <StatusBadge status={(a?.status || 'pending') as any} />
                          <div className="text-xs text-gray-600">Attempt {a?.attempt_no || 1} of {total}</div>
                        </div>
                        <div className="text-xs text-gray-600 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 w-full md:w-auto md:max-w-[70%] px-2">
                          <div><span className="text-gray-500">Started:</span> {a?.started_at ? new Date(a.started_at).toLocaleTimeString() : '—'}</div>
                          <div><span className="text-gray-500">Finished:</span> {a?.finished_at ? new Date(a.finished_at).toLocaleTimeString() : '—'}</div>
                          <div><span className="text-gray-500">Duration:</span> {fmtDur(dur)}</div>
                          <div><span className="text-gray-500">HTTP:</span> {a?.http_status ?? '—'}</div>
                          <div className="col-span-2"><span className="text-gray-500">Provider ID:</span> {a?.provider_request_id || '—'}</div>
                          {a?.response_payload && (
                            <div className="col-span-2">
                              <details>
                                <summary className="cursor-pointer select-none text-gray-700">Response payload</summary>
                                <pre className="text-[11px] bg-gray-50 p-2 rounded overflow-auto max-h-40">{JSON.stringify(a.response_payload, null, 2)}</pre>
                              </details>
                            </div>
                          )}
                          {a?.error_message && (
                            <div className="col-span-2 text-red-600">Error: {a.error_message}</div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {a?.status === 'failed' && (
                            <Button variant="outline" onClick={() => retry(key)} disabled={!!retrying[key]}>{retrying[key] ? 'Retrying…' : 'Retry'}</Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </CardContent>
              </Card>

              {/* Audit trail */}
              <Card>
                <CardHeader><CardTitle>Audit Trail</CardTitle></CardHeader>
                <CardContent>
                  {events.length === 0 ? (
                    <div className="text-sm text-gray-600">No events recorded.</div>
                  ) : (
                    <div className="relative">
                      <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-200" aria-hidden="true"></div>
                      <ul className="space-y-3">
                        {events.map((ev, i) => (
                          <li key={i} className="relative pl-8">
                            <div className="absolute left-1.5 top-1 w-3 h-3 rounded-full bg-blue-500" aria-hidden="true"></div>
                            <div className="text-sm">
                              <div className="flex items-center justify-between">
                                <div className="font-medium">{ev.action}</div>
                                <div className="text-gray-500">{new Date(ev.occurred_at).toLocaleString()}</div>
                              </div>
                              <div className="text-gray-600">{ev.component} • {ev.level}</div>
                              {ev.details && (
                                <pre className="text-[11px] bg-gray-50 p-2 rounded overflow-auto max-h-40 mt-1">{JSON.stringify(ev.details, null, 2)}</pre>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
