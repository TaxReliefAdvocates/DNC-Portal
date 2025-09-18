import React, { useEffect, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'

type RequestRow = {
  id: number
  phone_e164: string
  status: string
  reason?: string
  channel?: string
  requested_by_user_id: number
  created_at?: string
}

interface Props { organizationId: number; adminUserId: number }

export const PendingRequestsWidget: React.FC<Props> = ({ organizationId, adminUserId }) => {
  const [rows, setRows] = useState<RequestRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const acquireAuthHeaders = async (): Promise<Record<string,string>> => {
    const h: Record<string,string> = { 'Content-Type': 'application/json', 'X-Org-Id': String(organizationId), 'X-User-Id': String(adminUserId), 'X-Role': 'superadmin' }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) h['Authorization'] = `Bearer ${token}`
      }
    } catch {}
    return h
  }

  const load = async () => {
    setError(null)
    setLoading(true)
    try {
      const headers = await acquireAuthHeaders()
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/org/${organizationId}?status=pending&limit=10`, { headers })
      const json: RequestRow[] = await resp.json()
      setRows(json || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pending requests')
    } finally { setLoading(false) }
  }

  useEffect(()=>{ load() }, [])

  const act = async (id: number, action: 'approve'|'deny') => {
    setError(null)
    try {
      const headers = await acquireAuthHeaders()
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${id}/${action}`, { method:'POST', headers, body: JSON.stringify({ notes: '' }) })
      if (!resp.ok) throw new Error('Action failed')
      setRows(prev => prev.filter(r => r.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending Requests</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between mb-2 text-sm">
          <div className="text-gray-600">Top 10 newest pending.</div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={load} disabled={loading}>Refresh</Button>
          </div>
        </div>
        {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
        {loading ? (
          <div className="space-y-2">{Array.from({length:5}).map((_,i)=>(<div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />))}</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No pending requests.</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => (
              <div key={r.id} className="p-2 border rounded flex items-center justify-between">
                <div className="text-sm">
                  <div className="font-medium">{r.phone_e164} • {r.channel || 'n/a'}</div>
                  <div className="text-gray-600">Reason: {r.reason || '—'}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={()=>act(r.id,'approve')}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={()=>act(r.id,'deny')}>Deny</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


