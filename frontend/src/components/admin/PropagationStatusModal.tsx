import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiCall } from '../../lib/api'
import { Button } from '../ui/button'
import { Progress } from '../ui/progress'
import { StatusBadge } from './StatusBadge'

type Attempt = {
  service_key: string
  status: 'pending'|'in_progress'|'success'|'failed'
  http_status?: number
  provider_request_id?: string
  started_at?: string
  finished_at?: string | null
  duration_seconds?: number
  error_message?: string | null
}

export const PropagationStatusModal: React.FC<{ requestId: number; phone: string; onClose: ()=>void }>
  = ({ requestId, phone, onClose }) => {
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [, setLoading] = useState(true)
  const [, setAggregate] = useState<any>({})
  const [retrying, setRetrying] = useState<Record<string, boolean>>({})

  const load = async () => {
    setLoading(true)
    try {
      const data = await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${requestId}/status`)
      setAggregate(data.aggregate || {})
      setAttempts(data.attempts || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId])

  const progress = useMemo(() => {
    const total = attempts.length || 5
    const done = attempts.filter(a => a.status === 'success' || a.status === 'failed').length
    return Math.round((done / total) * 100)
  }, [attempts])

  const formatDur = (s?: number) => {
    if (!s && s !== 0) return ''
    return `${s.toFixed(1)}s`
  }

  const retry = async (service: string) => {
    setRetrying(prev => ({ ...prev, [service]: true }))
    try {
      // Attempt-specific retry endpoint expected by AdminPropagationMonitor retry() logic
      // Reuse same backend route shape used elsewhere: POST /api/v1/tenants/propagation/retry
      await apiCall(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId, service_key: service, phone_e164: phone })
      })
      // Optimistically mark as in_progress; next poll will update
      setAttempts(prev => prev.map(a => a.service_key === service ? { ...a, status: 'in_progress', finished_at: null, error_message: undefined } : a))
      await load()
    } catch (e) {
      // keep retry available; show toast could be added by parent
    } finally {
      setRetrying(prev => ({ ...prev, [service]: false }))
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-2xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold">Propagating… Request #{requestId} • {phone}</div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>
        <div className="mb-3">
          <div className="text-sm text-gray-700 mb-1">Progress: {progress}%</div>
          <Progress value={progress} />
        </div>
        <div className="border rounded">
          {['ringcentral','convoso','ytel','logics','genesys'].map(key => {
            const a = attempts.find(x => x.service_key === key)
            const st = a?.status || 'pending'
            return (
              <div key={key} className="flex items-center justify-between px-3 py-2 border-b last:border-b-0">
                <div className="flex items-center gap-2">
                  <div className="w-28 font-medium capitalize">{key}</div>
                  <StatusBadge status={st as any} />
                </div>
                <div className="text-xs text-gray-600">
                  {a?.finished_at ? new Date(a.finished_at).toLocaleTimeString() : (a?.started_at ? 'In progress…' : 'Pending…')}
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-xs text-gray-600 w-12 text-right">{formatDur(a?.duration_seconds)}</div>
                  {st === 'failed' && (
                    <Button
                      variant="outline"
                      onClick={() => retry(key)}
                      disabled={!!retrying[key]}
                    >
                      {retrying[key] ? 'Retrying…' : 'Retry'}
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  )
}


