import { API_BASE_URL } from '@/lib/api'
import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'

interface Props {
  organizationId: number
  adminUserId: number
  request: { id: number; phone_e164: string; channel?: string; reason?: string; requested_by_user_id: number; created_at?: string }
  onBack: () => void
}

export const AdminRequestDetail: React.FC<Props> = ({ organizationId, adminUserId, request, onBack }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [precheck, setPrecheck] = useState<any | null>(null)
  const [cases, setCases] = useState<any[]>([])
  const [notes, setNotes] = useState('')

  const headers = {
    'Content-Type': 'application/json',
    'X-Org-Id': String(organizationId),
    'X-User-Id': String(adminUserId),
    'X-Role': 'owner',
  }

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true)
      setError(null)
      try {
        const pre = await fetch(`${API_BASE_URL}/api/dnc/check_batch`, { method:'POST', headers, body: JSON.stringify({ phone_numbers: [request.phone_e164] }) })
        if (pre.ok) setPrecheck(await pre.json())
        const c = await fetch(`${API_BASE_URL}/api/dnc/cases_by_phone`, { method:'POST', headers, body: JSON.stringify({ phone_number: request.phone_e164 }) })
        if (c.ok) {
          const cj = await c.json()
          setCases(Array.isArray(cj.cases) ? cj.cases : [])
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load details')
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request.id])

  const act = async (action: 'approve'|'deny') => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${request.id}/${action}`, { method:'POST', headers, body: JSON.stringify({ reviewed_by_user_id: adminUserId, notes }) })
      if (!resp.ok) throw new Error('Action failed')
      onBack()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Request #{request.id}</h2>
        <Button variant="outline" onClick={onBack}>Back</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Request Info</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            <div><span className="font-medium">Phone:</span> {request.phone_e164}</div>
            <div><span className="font-medium">Channel:</span> {request.channel || 'n/a'}</div>
            <div><span className="font-medium">Reason:</span> {request.reason || '—'}</div>
            <div><span className="font-medium">Requested by:</span> #{request.requested_by_user_id}</div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>DNC Pre-check</CardTitle></CardHeader>
          <CardContent>
            {loading ? 'Loading…' : precheck ? (
              <div className="text-sm">
                <div>Total Checked: {precheck.total_checked} • Matches: {precheck.dnc_matches} • Safe: {precheck.safe_to_call}</div>
                <div className="mt-2 max-h-48 overflow-y-auto divide-y">
                  {precheck.results?.map((r:any,i:number)=> (
                    <div key={i} className="py-1 flex items-center justify-between">
                      <span>{r.phone_number}</span>
                      <span className={`text-xs ${r.is_dnc?'text-red-700':'text-green-700'}`}>{r.is_dnc?'DNC':'Safe'}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-gray-600 text-sm">No data</div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>TPS Cases</CardTitle></CardHeader>
          <CardContent>
            {loading ? 'Loading…' : cases.length ? (
              <div className="text-sm max-h-48 overflow-y-auto divide-y">
                {cases.map((c:any,idx:number)=> (
                  <div key={idx} className="py-1 flex items-center justify-between">
                    <div>
                      <div className="font-medium">Case {c.CaseID}</div>
                      <div className="text-xs text-gray-600">Created: {c.CreatedDate || '—'} • Last Modified: {c.LastModifiedDate || '—'}</div>
                    </div>
                    <div className="text-xs text-gray-700">{c.StatusName || `Status ${c.StatusID}`}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-600 text-sm">No cases found</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Decision</CardTitle></CardHeader>
        <CardContent>
          {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
          <div className="flex items-center gap-2">
            <Input placeholder="Decision notes (optional)" value={notes} onChange={(e)=>setNotes(e.target.value)} />
            <Button onClick={()=>act('approve')} className="bg-green-600 hover:bg-green-700">Approve</Button>
            <Button variant="outline" onClick={()=>act('deny')}>Deny</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}


