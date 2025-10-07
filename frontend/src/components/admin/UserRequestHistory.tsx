import { API_BASE_URL } from '@/lib/api'
import React, { useEffect, useState } from 'react'
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

interface Props { userId: number }

export const UserRequestHistory: React.FC<Props> = ({ userId }) => {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [cursor, setCursor] = useState<number | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [meId, setMeId] = useState<number | null>(null)

  const acquireAuthHeaders = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
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

  useEffect(() => {
    const run = async (append=false) => {
      setLoading(true)
      try {
        // Resolve current user id from backend; prefer freshly fetched value within this call
        let resolvedUserId: number | null = meId
        try {
          const headers = await acquireAuthHeaders()
          const meResp = await fetch(`${API_BASE_URL}/api/v1/tenants/auth/me`, { headers })
          if (meResp.ok) {
            const me = await meResp.json()
            if (me?.user_id) {
              resolvedUserId = Number(me.user_id)
              if (meId !== resolvedUserId) setMeId(resolvedUserId)
            }
          }
        } catch {}
        const params = new URLSearchParams()
        if (status) params.set('status', status)
        if (channel) params.set('channel', channel)
        if (cursor) params.set('cursor', String(cursor))
        params.set('limit','50')
        const headers = await acquireAuthHeaders()
        const targetUserId = resolvedUserId || meId || userId
        const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/user/${targetUserId}?${params.toString()}`, { headers })
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
  }, [userId, status, channel, meId])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your DNC Requests</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <Label className="text-sm font-medium text-gray-700">Status</Label>
            <select 
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
              value={status} 
              onChange={(e)=>setStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="denied">Denied</option>
            </select>
          </div>
          <div>
            <Label className="text-sm font-medium text-gray-700">Channel</Label>
            <select 
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
              value={channel} 
              onChange={(e)=>setChannel(e.target.value)}
            >
              <option value="">All Channels</option>
              <option value="voice">Voice</option>
              <option value="sms">SMS</option>
              <option value="email">Email</option>
            </select>
          </div>
          <div className="flex items-end">
            <button 
              className="w-full px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              onClick={() => {
                setStatus('')
                setChannel('')
              }}
            >
              Clear Filters
            </button>
          </div>
        </div>
        {loading ? (
          <div className="text-sm text-gray-600">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No requests yet.</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => {
              const getStatusBadge = (status: string) => {
                switch (status.toLowerCase()) {
                  case 'approved':
                    return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800 font-medium">Approved</span>
                  case 'pending':
                    return <span className="px-2 py-1 rounded text-xs bg-yellow-100 text-yellow-800 font-medium">Pending</span>
                  case 'denied':
                    return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800 font-medium">Denied</span>
                  default:
                    return <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-800 font-medium">{status}</span>
                }
              }
              
              return (
                <div key={r.id} className="flex items-center justify-between p-3 border rounded hover:bg-gray-50">
                  <div className="text-sm flex-1">
                    <div className="font-medium text-gray-900">{r.phone_e164} • {r.channel || 'n/a'}</div>
                    <div className="flex items-center gap-2 mt-1">
                      {getStatusBadge(r.status)}
                      <span className="text-gray-500 text-xs">• user request</span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 ml-4">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                  </div>
                </div>
              )
            })}
            {hasMore && (
              <div className="text-center pt-4">
                <button 
                  className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  onClick={()=>{
                    const runMore = async ()=>{
                      const headers = await acquireAuthHeaders()
                      const targetUserId = meId || userId
                      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/user/${targetUserId}?cursor=${cursor||''}&limit=50`, { headers })
                      const more: Row[] = await resp.json()
                      setRows([...rows, ...more])
                      setHasMore(more.length===50)
                      setCursor(more.length ? more[more.length-1].id : null)
                    }
                    runMore()
                  }}
                >
                  Load More
                </button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


