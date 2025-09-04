import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

type Row = {
  id: number
  organization_id: number
  phone_e164: string
  status: string
  reason?: string
  channel?: string
  created_at?: string
  decided_at?: string | null
}

interface Props {
  userId: number
}

export const UserRequestHistory: React.FC<Props> = ({ userId }) => {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)

  const headers = { 'X-User-Id': String(userId), 'X-Role': 'member' }

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      try {
        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/dnc-requests/user/${userId}`, { headers })
        const json = await resp.json()
        setRows(json)
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [userId])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your DNC Requests</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-sm text-gray-600">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No requests yet.</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                <div className="text-sm">
                  <div className="font-medium">{r.phone_e164} • {r.channel || 'n/a'}</div>
                  <div className="text-gray-600">{r.status} • {r.reason || '—'}</div>
                </div>
                <div className="text-xs text-gray-600">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


