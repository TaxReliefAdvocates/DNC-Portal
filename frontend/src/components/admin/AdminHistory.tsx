import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiCall } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { StatusBadge } from './StatusBadge'
import { RequestDetailsModal } from './RequestDetailsModal'

type Row = {
  id: number
  organization_id?: number
  phone_e164: string
  status: string
  requested_by_user_id?: number
  reviewed_by_user_id?: number
  created_at?: string
  decided_at?: string | null
}

export const AdminHistory: React.FC<{ organizationId: number }>= ({ organizationId }) => {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [detailsFor, setDetailsFor] = useState<number|null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      params.set('limit','200')
      const data: Row[] = await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/org/${organizationId}?${params.toString()}`)
      setRows(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [status])

  const filtered = useMemo(() => rows.filter(r => !q || (r.phone_e164||'').includes(q)), [rows, q])

  const exportCsv = () => {
    const header = ['Request ID','Phone','Status','Requested By','Approved By','Submitted','Completed']
    const lines = filtered.map(r => [r.id, r.phone_e164, r.status, r.requested_by_user_id||'', r.reviewed_by_user_id||'', r.created_at||'', r.decided_at||''])
    const csv = [header, ...lines]
      .map(cols => cols
        .map(x => {
          const s = String(x ?? '')
          const escaped = s.replace(/"/g, '""')
          return `"${escaped}"`
        })
        .join(',')
      )
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'dnc_history.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>DNC History</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-3">
          <div className="md:col-span-2">
            <Label>Search phone</Label>
            <Input value={q} onChange={e=>setQ(e.target.value)} placeholder="digits" />
          </div>
          <div>
            <Label>Status</Label>
            <select className="w-full border rounded px-2 py-1" value={status} onChange={e=>setStatus(e.target.value)}>
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="denied">Denied</option>
              <option value="completed">Completed</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <Button onClick={load} disabled={loading}>Refresh</Button>
            <Button variant="outline" onClick={exportCsv}>Export CSV</Button>
          </div>
        </div>

        {/* Table */}
        {loading ? (
          <div className="text-sm text-gray-600">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="text-sm text-gray-600">No requests found. Try adjusting your filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border">
              <thead>
                <tr className="bg-gray-50">
                  <th className="p-2 text-left">Request ID</th>
                  <th className="p-2 text-left">Phone</th>
                  <th className="p-2 text-left">Status</th>
                  <th className="p-2 text-left">Requested By</th>
                  <th className="p-2 text-left">Approved By</th>
                  <th className="p-2 text-left">Submitted</th>
                  <th className="p-2 text-left">Completed</th>
                  <th className="p-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(r => (
                  <tr key={r.id} className="border-t hover:bg-gray-50">
                    <td className="p-2">#{r.id}</td>
                    <td className="p-2">{r.phone_e164}</td>
                    <td className="p-2"><StatusBadge status={(r.status as any)} /></td>
                    <td className="p-2">{r.requested_by_user_id || '—'}</td>
                    <td className="p-2">{r.reviewed_by_user_id || '—'}</td>
                    <td className="p-2">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                    <td className="p-2">{r.decided_at ? new Date(r.decided_at).toLocaleString() : '—'}</td>
                    <td className="p-2"><Button variant="outline" onClick={() => setDetailsFor(r.id)}>View Details</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {detailsFor != null && (
          <RequestDetailsModal requestId={detailsFor} onClose={() => setDetailsFor(null)} />
        )}
      </CardContent>
    </Card>
  )
}


