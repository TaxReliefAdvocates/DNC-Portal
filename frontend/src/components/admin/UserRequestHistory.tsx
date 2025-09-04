import React, { useEffect, useState } from 'react'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
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
  const [status, setStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [cursor, setCursor] = useState<number | null>(null)
  const [hasMore, setHasMore] = useState(false)

  const headers = { 'X-User-Id': String(userId), 'X-Role': 'member' }

  useEffect(() => {
    const run = async (append=false) => {
      setLoading(true)
      try {
        const params = new URLSearchParams()
        if (status) params.set('status', status)
        if (cursor) params.set('cursor', String(cursor))
        params.set('limit','50')
        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/dnc-requests/user/${userId}?${params.toString()}`, { headers })
        const newRows: Row[] = await resp.json()
        setRows(append ? [...rows, ...newRows] : newRows)
        setHasMore(newRows.length===50)
        setCursor(newRows.length ? newRows[newRows.length-1].id : null)
      } finally {
        setLoading(false)
      }
    }
    setCursor(null)
    run(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, status])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your DNC Requests</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <div>
            <Label className="text-xs">Status</Label>
            <select className="w-full border rounded px-2 py-1" value={status} onChange={(e)=>setStatus(e.target.value)}>
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="denied">Denied</option>
            </select>
          </div>
          <div>
            <Label className="text-xs">Channel</Label>
            <select className="w-full border rounded px-2 py-1" value={channel} onChange={(e)=>setChannel(e.target.value)}>
              <option value="">Any</option>
              <option value="voice">Voice</option>
              <option value="sms">SMS</option>
              <option value="email">Email</option>
            </select>
          </div>
        </div>
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
            {hasMore && (
              <div className="text-center pt-2">
                <button className="px-3 py-1 border rounded" onClick={()=>{
                  const runMore = async ()=>{
                    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/dnc-requests/user/${userId}?cursor=${cursor||''}&limit=50`, { headers })
                    const more: Row[] = await resp.json()
                    setRows([...rows, ...more])
                    setHasMore(more.length===50)
                    setCursor(more.length ? more[more.length-1].id : null)
                  }
                  runMore()
                }}>Load more</button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


