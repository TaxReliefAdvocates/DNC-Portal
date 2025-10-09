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
  const [systemsCheck, setSystemsCheck] = useState<any | null>(null)
  const [logicsCases, setLogicsCases] = useState<any[]>([])
  const [notes, setNotes] = useState('')

  const acquireAuthHeaders = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Org-Id': String(organizationId),
      'X-User-Id': String(adminUserId),
      'X-Role': 'superadmin',
    }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[]) => Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) h['Authorization'] = `Bearer ${token}`
      }
    } catch {}
    return h
  }

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true)
      setError(null)
      try {
        const headers = await acquireAuthHeaders()
        
        // Fetch Systems Check results (same as Systems Check pane)
        const systemsCheckData: Record<string, any> = {}
        
        // 1) FreeDNC API check
        try {
          const fj = await fetch(`${API_BASE_URL}/api/check_number`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (fj.ok) {
            const fjData = await fj.json()
            systemsCheckData.dnc = { listed: Boolean(fjData?.is_dnc) }
          }
        } catch {}

        // 2) RingCentral search
        try {
          const rc = await fetch(`${API_BASE_URL}/api/v1/ringcentral/search-dnc`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (rc.ok) {
            const rj = await rc.json()
            const isOnDnc = rj?.data?.is_on_dnc
            if (isOnDnc === null) {
              systemsCheckData.ringcentral = { listed: null, status: 'unknown' }
            } else {
              systemsCheckData.ringcentral = { listed: isOnDnc || false }
            }
          }
        } catch {}

        // 3) Convoso search
        try {
          const cv = await fetch(`${API_BASE_URL}/api/v1/convoso/search-dnc`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (cv.ok) {
            const cj = await cv.json()
            const isOnDnc = cj?.data?.is_on_dnc
            if (isOnDnc === null) {
              systemsCheckData.convoso = { listed: null, status: 'unknown' }
            } else {
              systemsCheckData.convoso = { listed: isOnDnc || false }
            }
          }
        } catch {}

        // 4) Ytel search
        try {
          const yt = await fetch(`${API_BASE_URL}/api/v1/ytel/search-dnc`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (yt.ok) {
            const yj = await yt.json()
            const isOnDnc = yj?.data?.is_on_dnc
            if (isOnDnc === null) {
              systemsCheckData.ytel = { listed: null, status: 'unknown' }
            } else {
              systemsCheckData.ytel = { listed: isOnDnc || false }
            }
          }
        } catch {}

        // 5) Logics search (for cases)
        try {
          const lj = await fetch(`${API_BASE_URL}/api/v1/logics/search-by-phone`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (lj.ok) {
            const ljData = await lj.json()
            const cases = ljData?.data?.raw_response?.Data || []
            systemsCheckData.logics = { 
              listed: cases.length > 0, 
              count: cases.length, 
              cases: cases 
            }
            setLogicsCases(cases)
          }
        } catch {}

        // 6) Genesys search
        try {
          const gj = await fetch(`${API_BASE_URL}/api/v1/genesys/search-dnc`, { 
            method:'POST', 
            headers, 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          if (gj.ok) {
            const gjData = await gj.json()
            const isOnDnc = gjData?.data?.is_on_dnc
            if (isOnDnc === null) {
              systemsCheckData.genesys = { listed: null, status: 'unknown' }
            } else {
              systemsCheckData.genesys = { listed: isOnDnc || false }
            }
          }
        } catch {}

        setSystemsCheck({ phone_number: request.phone_e164, providers: systemsCheckData })
        
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
      const headers = await acquireAuthHeaders()
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${request.id}/${action}`, { method:'POST', headers, body: JSON.stringify({ notes }) })
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
          <CardHeader><CardTitle>Systems Check</CardTitle></CardHeader>
          <CardContent>
            {loading ? 'Loading…' : systemsCheck ? (
              <div className="text-sm space-y-2">
                {/* National DNC */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">National DNC</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.dnc?.listed === true ? (
                      <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                    ) : systemsCheck.providers?.dnc?.listed === false ? (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                  </div>
                </div>
                
                {/* RingCentral */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">RingCentral</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.ringcentral?.listed === true ? (
                      <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                    ) : systemsCheck.providers?.ringcentral?.listed === false ? (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                  </div>
                </div>
                
                {/* Convoso */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">Convoso</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.convoso?.listed === true ? (
                      <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                    ) : systemsCheck.providers?.convoso?.listed === false ? (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                  </div>
                </div>
                
                {/* Ytel */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">Ytel</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.ytel?.listed === true ? (
                      <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                    ) : systemsCheck.providers?.ytel?.listed === false ? (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                  </div>
                </div>
                
                {/* Genesys */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">Genesys</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.genesys?.listed === true ? (
                      <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                    ) : systemsCheck.providers?.genesys?.listed === false ? (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-gray-600 text-sm">No data</div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Logics Cases</CardTitle></CardHeader>
          <CardContent>
            {loading ? 'Loading…' : logicsCases.length ? (
              <div className="text-sm max-h-48 overflow-y-auto divide-y">
                {logicsCases.map((c:any,idx:number)=> (
                  <div key={idx} className="py-2 border-b last:border-b-0">
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="font-medium text-gray-700">Case ID:</span>
                        <span className="ml-1 text-gray-900">{c.CaseID || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700">Status ID:</span>
                        <span className="ml-1 text-gray-900">{c.StatusID || 'N/A'}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="font-medium text-gray-700">Name:</span>
                        <span className="ml-1 text-gray-900">
                          {[c.FirstName, c.MiddleName, c.LastName]
                            .filter(Boolean)
                            .join(' ') || 'N/A'}
                        </span>
                      </div>
                      {c.Email && (
                        <div className="col-span-2">
                          <span className="font-medium text-gray-700">Email:</span>
                          <span className="ml-1 text-gray-900">{c.Email}</span>
                        </div>
                      )}
                      {c.CreatedDate && (
                        <div className="col-span-2">
                          <span className="font-medium text-gray-700">Created:</span>
                          <span className="ml-1 text-gray-900">{new Date(c.CreatedDate).toLocaleString()}</span>
                        </div>
                      )}
                      {c.TaxAmount && (
                        <div className="col-span-2">
                          <span className="font-medium text-gray-700">Tax Amount:</span>
                          <span className="ml-1 text-gray-900">${c.TaxAmount.toLocaleString()}</span>
                        </div>
                      )}
                    </div>
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


