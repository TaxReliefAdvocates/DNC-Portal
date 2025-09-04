import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'

type RequestRow = {
  id: number
  phone_e164: string
  status: string
  reason?: string
  channel?: string
  requested_by_user_id: number
  reviewed_by_user_id?: number
  created_at?: string
  decided_at?: string | null
}

interface Props {
  organizationId: number
  adminUserId: number
}

export const AdminDncRequests: React.FC<Props> = ({ organizationId, adminUserId }) => {
  const [rows, setRows] = useState<RequestRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const headers = {
    'Content-Type': 'application/json',
    'X-Org-Id': String(organizationId),
    'X-User-Id': String(adminUserId),
    'X-Role': 'owner',
  }

  const fetchPending = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/dnc-requests/org/${organizationId}?status=pending`, { headers })
      if (!resp.ok) throw new Error('Failed to load requests')
      const json = await resp.json()
      setRows(json)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPending()
  }, [])

  const act = async (reqId: number, action: 'approve' | 'deny') => {
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/dnc-requests/${reqId}/${action}`,
        { method: 'POST', headers, body: JSON.stringify({ reviewed_by_user_id: adminUserId }) })
      if (!resp.ok) throw new Error('Action failed')
      await fetchPending()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending DNC Requests</CardTitle>
      </CardHeader>
      <CardContent>
        {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
        {loading ? (
          <div className="text-sm text-gray-600">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No pending requests</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                <div className="text-sm">
                  <div className="font-medium">{r.phone_e164} • {r.channel || 'n/a'}</div>
                  <div className="text-gray-600">Reason: {r.reason || '—'} • Requested by #{r.requested_by_user_id}</div>
                </div>
                <div className="flex gap-2">
                  <Button className="bg-green-600 hover:bg-green-700" onClick={() => act(r.id, 'approve')}>Approve</Button>
                  <Button variant="outline" onClick={() => act(r.id, 'deny')}>Deny</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


