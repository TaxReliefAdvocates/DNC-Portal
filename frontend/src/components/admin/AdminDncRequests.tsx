import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { toast } from 'sonner'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { AdminRequestDetail } from './AdminRequestDetail'
import { useAppSelector } from '../../lib/hooks'

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
  const role = useAppSelector((s)=>s.demoAuth.role)
  const [rows, setRows] = useState<RequestRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<'pending'|'approved'|'denied'|''>('pending')
  const [query, setQuery] = useState('')
  const [channel, setChannel] = useState('')
  const [requester, setRequester] = useState('')
  const [cursor, setCursor] = useState<number | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [selected, setSelected] = useState<Record<number, boolean>>({})
  const [decisionNotes, setDecisionNotes] = useState('')
  const [userMap, setUserMap] = useState<Record<number,{id:number,email:string,name?:string}>>({})

  const [activeRequest, setActiveRequest] = useState<RequestRow | null>(null)

  const baseHeaders = {
    'Content-Type': 'application/json',
    'X-Org-Id': String(organizationId),
    'X-User-Id': String(adminUserId),
    'X-Role': role === 'superadmin' ? 'superadmin' : 'admin',
  }

  const withAuth = async (headers: Record<string,string>) => {
    const out = { ...headers }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) out['Authorization'] = `Bearer ${token}`
      }
    } catch {}
    return out
  }

  const fetchPending = async (append=false) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      // Only include cursor when we are appending; a fresh reload should start from the beginning
      if (append && cursor) params.set('cursor', String(cursor))
      params.set('limit','50')
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/org/${organizationId}?${params.toString()}`, { headers: await withAuth(baseHeaders) })
      if (!resp.ok) throw new Error('Failed to load requests')
      const newRows: RequestRow[] = await resp.json()
      setRows(append ? [...rows, ...newRows] : newRows)
      setHasMore(newRows.length === 50)
      setCursor(newRows.length ? newRows[newRows.length-1].id : null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setCursor(null)
    fetchPending(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  // Load users for name/email lookup
  useEffect(() => {
    (async()=>{
      try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/users`)
        if (!resp.ok) return
        const list: Array<{id:number,email:string,name?:string}> = await resp.json()
        const m: Record<number,{id:number,email:string,name?:string}> = {}
        list.forEach(u=>{ m[u.id]=u })
        setUserMap(m)
      } catch {}
    })()
  }, [])

  const act = async (reqId: number, action: 'approve' | 'deny') => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${reqId}/${action}`,
        { method: 'POST', headers: await withAuth(baseHeaders), body: JSON.stringify({ notes: decisionNotes }) })
      if (!resp.ok) throw new Error('Action failed')
      await fetchPending(false)
      toast.success(action === 'approve' ? 'Request approved' : 'Request denied')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
      toast.error('Action failed')
    }
  }

  const selectedIds = useMemo(()=> Object.entries(selected).filter(([,v])=>v).map(([k])=> Number(k)), [selected])

  const bulk = async (action: 'approve'|'deny') => {
    if (selectedIds.length===0) return
    try {
      const url = `${API_BASE_URL}/api/v1/tenants/dnc-requests/bulk/${action}`
      const resp = await fetch(url, { method:'POST', headers: await withAuth(baseHeaders), body: JSON.stringify({ ids: selectedIds, notes: decisionNotes }) })
      if (!resp.ok) throw new Error('Bulk action failed')
      setSelected({})
      await fetchPending(false)
      toast.success(`${action==='approve'?'Approved':'Denied'} ${selectedIds.length} requests`)
    } catch {
      toast.error('Bulk action failed')
    }
  }

  if (activeRequest) {
    return (
      <AdminRequestDetail
        organizationId={organizationId}
        adminUserId={adminUserId}
        request={activeRequest}
        onBack={() => { setActiveRequest(null); fetchPending(false) }}
      />
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending DNC Requests</CardTitle>
      </CardHeader>
      <CardContent>
        {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
        {/* Controls */}
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mb-3">
          <div>
            <Label className="text-xs">Status</Label>
            <select className="w-full border rounded px-2 py-1" value={status} onChange={(e)=>setStatus(e.target.value as any)}>
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
          <div>
            <Label className="text-xs">Requester</Label>
            <Input value={requester} onChange={(e)=>setRequester(e.target.value)} placeholder="name or email" />
          </div>
          <div className="md:col-span-2">
            <Label className="text-xs">Search phone</Label>
            <Input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="digits only" />
          </div>
        </div>
        {/* Bulk actions */}
        <div className="flex items-center gap-2 mb-3">
          <Input placeholder="Decision notes (optional)" value={decisionNotes} onChange={(e)=>setDecisionNotes(e.target.value)} />
          <Button variant="outline" onClick={()=>bulk('approve')} disabled={selectedIds.length===0}>Approve selected</Button>
          <Button variant="outline" onClick={()=>bulk('deny')} disabled={selectedIds.length===0}>Deny selected</Button>
        </div>
        {loading && rows.length===0 ? (
          <div className="space-y-2">
            {Array.from({length:5}).map((_,i)=> (<div key={i} className="animate-pulse h-10 bg-gray-100 rounded" />))}
          </div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No pending requests</div>
        ) : (
          <div className="space-y-2">
            {rows
              .filter(r => {
                if (query && !r.phone_e164.includes(query)) return false
                if (channel && r.channel!==channel) return false
                if (requester) {
                  const u = userMap[r.requested_by_user_id]
                  const hay = `${u?.name||''} ${u?.email||''}`.toLowerCase()
                  if (!hay.includes(requester.toLowerCase())) return false
                }
                return true
              })
              .map(r => (
              <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={!!selected[r.id]} onChange={(e)=>setSelected({...selected, [r.id]: e.target.checked})} />
                  <div className="text-sm">
                    <div className="font-medium">{r.phone_e164} • {r.channel || 'n/a'}</div>
                    <div className="text-gray-600">Reason: {r.reason || '—'} • Requested by {userMap[r.requested_by_user_id]?.name || 'User'}{userMap[r.requested_by_user_id]?.email ? ` (${userMap[r.requested_by_user_id]?.email})` : ''}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setActiveRequest(r)}>View</Button>
                  <Button className="bg-green-600 hover:bg-green-700" onClick={() => act(r.id, 'approve')}>Approve</Button>
                  <Button variant="outline" onClick={() => act(r.id, 'deny')}>Deny</Button>
                </div>
              </div>
            ))}
            {hasMore && (
              <div className="text-center pt-2">
                <Button variant="outline" onClick={()=>fetchPending(true)}>Load more</Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


