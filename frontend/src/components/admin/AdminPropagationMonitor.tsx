import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { useAppSelector } from '@/lib/hooks'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'

type Attempt = {
  id: number
  organization_id: number
  job_item_id: number | null
  phone_e164: string
  service_key: string
  attempt_no: number
  status: 'pending' | 'success' | 'failed'
  error_message?: string | null
  request_payload?: any
  response_payload?: any
  started_at: string
  finished_at?: string | null
}

type RequestRow = {
  id: number
  phone_e164: string
  status: string
  reason?: string
  channel?: string
  requested_by_user_id: number
  reviewed_by_user_id?: number | null
  created_at?: string
  decided_at?: string | null
}

type UserRow = { id: number; email: string; name?: string | null }

interface Props { organizationId: number; adminUserId: number }

export const AdminPropagationMonitor: React.FC<Props> = ({ organizationId, adminUserId }) => {
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [requests, setRequests] = useState<RequestRow[]>([])
  const [users, setUsers] = useState<Record<number, UserRow>>({})
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')
  const [provider, setProvider] = useState('')
  const [status, setStatus] = useState('')
  const role = useAppSelector((s) => (s as any).demoAuth?.role || 'member')

  const acquireAuthHeaders = async (): Promise<Record<string,string>> => {
    const h: Record<string,string> = {
      'Content-Type': 'application/json',
      'X-Org-Id': String(organizationId),
      'X-User-Id': String(adminUserId),
      'X-Role': 'superadmin',
    }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) h['Authorization'] = `Bearer ${token}`
      }
    } catch (error) {
      console.warn('Failed to acquire token:', error)
    }
    return h
  }

  const load = async () => {
    setLoading(true)
    try {
      const headers = await acquireAuthHeaders()
      
      // Fetch propagation attempts
      try {
        const a = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/attempts/${organizationId}`, { headers })
        if (a.ok) {
          const attemptsJson: Attempt[] = await a.json()
          setAttempts(attemptsJson || [])
        } else {
          console.warn('Failed to fetch propagation attempts:', a.status, a.statusText)
          setAttempts([])
        }
      } catch (error) {
        console.error('Error fetching propagation attempts:', error)
        setAttempts([])
      }

      // Fetch DNC requests
      try {
        const r = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/org/${organizationId}?limit=500`, { headers })
        if (r.ok) {
          const reqJson: RequestRow[] = await r.json()
          setRequests(reqJson || [])
        } else {
          console.warn('Failed to fetch DNC requests:', r.status, r.statusText)
          setRequests([])
        }
      } catch (error) {
        console.error('Error fetching DNC requests:', error)
        setRequests([])
      }

      // Fetch users
      try {
        const u = await fetch(`${API_BASE_URL}/api/v1/tenants/users`, { headers })
        if (u.ok) {
          const list: UserRow[] = await u.json()
          const m: Record<number, UserRow> = {}
          list.forEach(u => { m[u.id] = u })
          setUsers(m)
        } else {
          console.warn('Failed to fetch users:', u.status, u.statusText)
        }
      } catch (error) {
        console.error('Error fetching users:', error)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(()=>{ load() }, [])

  const rows = useMemo(()=>{
    // Group attempts by phone
    const group: Record<string, Attempt[]> = {}
    attempts.forEach(a => {
      if (q && !a.phone_e164.includes(q)) return
      if (provider && a.service_key !== provider) return
      if (status && a.status !== status) return
      if (!group[a.phone_e164]) group[a.phone_e164] = []
      group[a.phone_e164].push(a)
    })
    // Map to summary with per-provider latest status
    const phones = Object.keys(group)
    const mappedRows = phones.map(phone => {
      const arr = group[phone].sort((x,y)=> (new Date(y.started_at).getTime()-new Date(x.started_at).getTime()))
      const byProvider: Record<string, Attempt | undefined> = {}
      arr.forEach(a => { if (!byProvider[a.service_key]) byProvider[a.service_key] = a })
      const req = requests.find(r => r.phone_e164 === phone)
      const adminFallback = users[adminUserId]
      const isSuperadmin = String(role).toLowerCase() === 'superadmin'
      
      // Get the most recent timestamp for sorting
      const mostRecentAttempt = arr[0] // Already sorted by most recent first
      const mostRecentTimestamp = mostRecentAttempt ? new Date(mostRecentAttempt.started_at).getTime() : 0
      
      return {
        phone,
        providers: byProvider,
        requested_by: req ? users[req.requested_by_user_id] : (isSuperadmin ? adminFallback : undefined),
        approved_by: req && req.reviewed_by_user_id ? users[req.reviewed_by_user_id] : (isSuperadmin ? adminFallback : undefined),
        decided_at: req?.decided_at,
        most_recent_timestamp: mostRecentTimestamp,
      }
    })
    
    // Sort by most recent timestamp first (newest to oldest)
    return mappedRows.sort((a, b) => b.most_recent_timestamp - a.most_recent_timestamp)
  }, [attempts, requests, users, q, provider, status])

  const providers = ['ringcentral','convoso','ytel','logics','genesys']

  const exportCsv = () => {
    const headers = ['phone','provider','status','attempt_no','started_at','finished_at','error','requested_by','approved_by']
    const lines: string[] = [headers.join(',')]
    rows.forEach(r => {
      providers.forEach(p => {
        const a = r.providers[p]
        if (!a) return
        lines.push([
          r.phone,
          p,
          a.status,
          String(a.attempt_no),
          a.started_at,
          a.finished_at || '',
          (a.error_message || '').replace(/\n|\r|,/g,' '),
          r.requested_by ? `${r.requested_by.email}` : '',
          r.approved_by ? `${r.approved_by.email}` : '',
        ].join(','))
      })
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'dnc_history_export.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const badge = (s?: string) => {
    if (!s) return <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">—</span>
    const cls = s==='success' ? 'bg-green-100 text-green-800' : s==='failed' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
    return <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>{s}</span>
  }

  const retry = async (providerKey: string, phone: string) => {
    try {
      const headers = await acquireAuthHeaders()
      let response: Response | null = null
      
      // Minimal: call provider-specific add endpoints where available
      if (providerKey === 'ringcentral') {
        response = await fetch(`${API_BASE_URL}/api/v1/ringcentral/dnc/add?phone_number=${encodeURIComponent(phone)}&label=${encodeURIComponent('API Block')}`, { method:'POST', headers })
      } else if (providerKey === 'convoso') {
        response = await fetch(`${API_BASE_URL}/api/v1/convoso/dnc/add?phone_number=${encodeURIComponent(phone)}`, { method:'POST', headers })
      } else if (providerKey === 'ytel') {
        response = await fetch(`${API_BASE_URL}/api/v1/ytel/dnc/add?phone_number=${encodeURIComponent(phone)}`, { method:'POST', headers })
      } else if (providerKey === 'logics') {
        // No generic push; rely on Systems Check flows. Skip here.
        console.log('Logics retry not implemented - use Systems Check flow')
        return
      }
      
      if (response && !response.ok) {
        console.error(`Retry failed for ${providerKey}:`, response.status, response.statusText)
      } else if (response) {
        console.log(`Retry successful for ${providerKey}`)
      }
      
      // After retry, reload attempts
      load()
    } catch (error) {
      console.error(`Error retrying ${providerKey}:`, error)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>DNC History Monitor</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-2 mb-3 text-sm">
          <div className="flex flex-col">
            <label>Search phone</label>
            <input className="border rounded px-2 py-1" placeholder="digits" value={q} onChange={(e)=>setQ(e.target.value)} />
          </div>
          <div className="flex flex-col">
            <label>Provider</label>
            <select className="border rounded px-2 py-1" value={provider} onChange={(e)=>setProvider(e.target.value)}>
              <option value="">Any</option>
              {providers.map(p=> <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="flex flex-col">
            <label>Status</label>
            <select className="border rounded px-2 py-1" value={status} onChange={(e)=>setStatus(e.target.value)}>
              <option value="">Any</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
              <option value="pending">pending</option>
            </select>
          </div>
          <Button onClick={load} disabled={loading}>Refresh</Button>
          <Button variant="outline" onClick={exportCsv}>Export CSV</Button>
        </div>

        {loading ? (
          <div className="text-sm text-gray-600">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-gray-600">No DNC history yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border">
              <thead>
                <tr className="bg-gray-50">
                  <th className="p-2 text-left">Phone</th>
                  <th className="p-2 text-left">Requested By</th>
                  <th className="p-2 text-left">Approved By</th>
                  <th className="p-2 text-left">Services</th>
                  <th className="p-2 text-left">Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r)=> (
                  <tr key={r.phone} className="border-t hover:bg-gray-50">
                    <td className="p-2 font-medium">{r.phone}</td>
                    <td className="p-2">{r.requested_by ? (r.requested_by.name || r.requested_by.email) : '—'}</td>
                    <td className="p-2">{r.approved_by ? (r.approved_by.name || r.approved_by.email) : '—'}</td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-1">
                        {providers.map(p=>{
                          const a = r.providers[p]
                          if (!a) return null
                          return (
                            <div key={p} className="flex items-center gap-1">
                              {badge(a.status)}
                              <span className="text-xs text-gray-600 capitalize">{p}</span>
                              {a.status === 'failed' && (
                                <button 
                                  className="text-xs text-blue-600 underline hover:text-blue-800" 
                                  onClick={()=>retry(p, r.phone)}
                                  title={`Retry ${p} for ${r.phone}`}
                                >
                                  Retry
                                </button>
                              )}
                            </div>
                          )
                        })}
                        {Object.keys(r.providers).length === 0 && (
                          <span className="text-xs text-gray-400">No services</span>
                        )}
                      </div>
                    </td>
                    <td className="p-2 text-xs text-gray-500">
                      {r.decided_at ? new Date(r.decided_at).toLocaleString() : 
                       Object.values(r.providers).find(a => a?.finished_at)?.finished_at ? 
                       new Date(Object.values(r.providers).find(a => a?.finished_at)!.finished_at!).toLocaleString() : 
                       '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}


