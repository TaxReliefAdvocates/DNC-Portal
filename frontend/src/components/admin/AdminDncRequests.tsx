import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL, apiCall } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { toast } from 'sonner'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { AdminRequestDetail } from './AdminRequestDetail'
import { ApproveRequestModal } from './ApproveRequestModal'
import { RejectRequestModal } from './RejectRequestModal'
import { PropagationStatusModal } from './PropagationStatusModal'
// import { useAppSelector } from '../../lib/hooks' // Not currently used

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
  // const role = useAppSelector((s)=>s.demoAuth.role) // Not currently used
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
  const [systemsChecks, setSystemsChecks] = useState<Record<string, any>>({})
  const [checkingSystems, setCheckingSystems] = useState<Set<string>>(new Set())
  const [processingRequests, setProcessingRequests] = useState<Set<number>>(new Set())
  const [approveModalFor, setApproveModalFor] = useState<RequestRow | null>(null)
  const [rejectModalFor, setRejectModalFor] = useState<RequestRow | null>(null)
  const [propModal, setPropModal] = useState<{ requestId: number, phone: string } | null>(null)

  // Removed baseHeaders - using apiCall instead

  // Removed withAuth function - using apiCall instead

  const fetchPending = async (append=false) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      // Only include cursor when we are appending; a fresh reload should start from the beginning
      if (append && cursor) params.set('cursor', String(cursor))
      params.set('limit','50')
      
      console.log('🔍 FETCHING PENDING REQUESTS:', {
        organizationId,
        status,
        cursor,
        append
      })
      
      const newRows: RequestRow[] = await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/org/${organizationId}?${params.toString()}`)
      
      console.log('✅ PENDING REQUESTS LOADED:', newRows)
      setRows(append ? [...rows, ...newRows] : newRows)
      setHasMore(newRows.length === 50)
      setCursor(newRows.length ? newRows[newRows.length-1].id : null)
    } catch (e) {
      console.error('❌ FAILED TO LOAD REQUESTS:', e)
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
        console.log('👥 LOADING USERS for organization:', organizationId)
        const list: Array<{id:number,email:string,name?:string}> = await apiCall(`${API_BASE_URL}/api/v1/tenants/users`)
        const m: Record<number,{id:number,email:string,name?:string}> = {}
        list.forEach(u=>{ m[u.id]=u })
        setUserMap(m)
        console.log('✅ USERS LOADED:', m)
      } catch (e) {
        console.error('❌ FAILED TO LOAD USERS:', e)
        setUserMap({})
      }
    })()
  }, [])

  const act = async (reqId: number, action: 'approve' | 'deny', notes?: string, propagateTo?: string[]) => {
    setProcessingRequests(prev => new Set(prev).add(reqId))
    try {
      console.log(`🚀 ${action.toUpperCase()} REQUEST:`, reqId)
      
      let url = `${API_BASE_URL}/api/v1/tenants/dnc-requests/${reqId}/${action}`
      let method = 'POST'
      // If backend expects PATCH /decide for approval, route accordingly
      if (action === 'approve') {
        url = `${API_BASE_URL}/api/v1/tenants/dnc-requests/${reqId}/decide`
        method = 'PATCH'
      }
      const body = action === 'approve'
        ? JSON.stringify({ decision: 'approved', notes: notes ?? decisionNotes, propagate_to: propagateTo || undefined })
        : JSON.stringify({ notes: notes ?? decisionNotes })
      const response = await apiCall(url, { method, body })
      
      console.log(`✅ ${action.toUpperCase()} SUCCESS:`, response)
      await fetchPending(false)
      toast.success(action === 'approve' ? 'Request approved successfully!' : 'Request denied')

      if (action === 'approve') {
        const r = rows.find(x => x.id === reqId)
        if (r) setPropModal({ requestId: r.id, phone: r.phone_e164 })
      }
    } catch (e) {
      console.error(`❌ ${action.toUpperCase()} FAILED:`, e)
      setError(e instanceof Error ? e.message : 'Action failed')
      toast.error(`${action === 'approve' ? 'Approval' : 'Denial'} failed`)
    } finally {
      setProcessingRequests(prev => {
        const newSet = new Set(prev)
        newSet.delete(reqId)
        return newSet
      })
    }
  }

  const selectedIds = useMemo(()=> Object.entries(selected).filter(([,v])=>v).map(([k])=> Number(k)), [selected])

  const bulk = async (action: 'approve'|'deny') => {
    if (selectedIds.length===0) return
    try {
      // For approval, check systems first for all selected requests
      if (action === 'approve') {
        toast.info(`Checking systems for ${selectedIds.length} requests before approval...`)
        const selectedRequests = rows.filter(r => selectedIds.includes(r.id))
        for (const request of selectedRequests) {
          await checkSystemsForPhone(request.phone_e164)
        }
        // Wait a moment for all systems checks to complete
        await new Promise(resolve => setTimeout(resolve, 3000))
      }
      
      const url = `${API_BASE_URL}/api/v1/tenants/dnc-requests/bulk/${action}`
      console.log(`🚀 BULK ${action.toUpperCase()}:`, selectedIds)
      
      const response = await apiCall(url, { 
        method:'POST', 
        body: JSON.stringify({ ids: selectedIds, notes: decisionNotes }) 
      })
      
      console.log(`✅ BULK ${action.toUpperCase()} SUCCESS:`, response)
      setSelected({})
      await fetchPending(false)
      toast.success(`${action==='approve'?'Approved':'Denied'} ${selectedIds.length} requests successfully!`)
    } catch (e) {
      console.error(`❌ BULK ${action.toUpperCase()} FAILED:`, e)
      toast.error(`Bulk ${action} failed: ${e instanceof Error ? e.message : 'Unknown error'}`)
    }
  }

  const checkSystemsForPhone = async (phone: string) => {
    if (checkingSystems.has(phone)) return
    
    setCheckingSystems(prev => new Set(prev).add(phone))
    
    const providers: Record<string, any> = {}
    
    try {
      // 1) FreeDNC API check
      try {
        const fj = await fetch(`${API_BASE_URL}/api/check_number`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (fj.ok) {
          const fjData = await fj.json()
          providers.dnc = { listed: Boolean(fjData?.is_dnc) }
        }
      } catch {}

      // 2) RingCentral search for number
      try {
        const rc = await fetch(`${API_BASE_URL}/api/v1/ringcentral/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (rc.ok) {
          const rj = await rc.json()
          const isOnDnc = rj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.ringcentral = { listed: null, status: 'unknown' }
          } else {
            providers.ringcentral = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 3) Convoso search-dnc
      try {
        const cv = await fetch(`${API_BASE_URL}/api/v1/convoso/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (cv.ok) {
          const cj = await cv.json()
          const isOnDnc = cj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.convoso = { listed: null, status: 'unknown' }
          } else {
            providers.convoso = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 4) Ytel search-dnc (two-step DNC check)
      try {
        const yt = await fetch(`${API_BASE_URL}/api/v1/ytel/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (yt.ok) {
          const yj = await yt.json()
          const isOnDnc = yj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.ytel = { listed: null, status: 'unknown' }
          } else {
            providers.ytel = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 5) Logics search-by-phone
      try {
        const lj = await fetch(`${API_BASE_URL}/api/v1/logics/search-by-phone`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (lj.ok) {
          const ljData = await lj.json()
          // Logics returns cases in data.raw_response.Data
          const cases = ljData?.data?.raw_response?.Data || []
          providers.logics = { 
            listed: cases.length > 0, 
            count: cases.length, 
            cases: cases 
          }
        }
      } catch {}

      // 6) Genesys search-dnc
      try {
        const gj = await fetch(`${API_BASE_URL}/api/v1/genesys/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: phone })
        })
        if (gj.ok) {
          const gjData = await gj.json()
          const isOnDnc = gjData?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.genesys = { listed: null, status: 'unknown' }
          } else {
            providers.genesys = { listed: isOnDnc || false }
          }
        }
      } catch {}

      setSystemsChecks(prev => ({
        ...prev,
        [phone]: { phone_number: phone, providers }
      }))
    } finally {
      setCheckingSystems(prev => {
        const newSet = new Set(prev)
        newSet.delete(phone)
        return newSet
      })
    }
  }

  const getStatusBadge = (listed?: boolean | null) => {
    if (listed === true) return <span className="px-1 py-0.5 rounded text-xs bg-green-100 text-green-800">On DNC</span>
    if (listed === false) return <span className="px-1 py-0.5 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
    return <span className="px-1 py-0.5 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
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
    <>
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
          <Button 
            variant="outline" 
            onClick={() => {
              const pendingPhones = rows.filter(r => r.status === 'pending').map(r => r.phone_e164)
              pendingPhones.forEach(phone => checkSystemsForPhone(phone))
            }}
            disabled={checkingSystems.size > 0}
          >
            Check All Systems
          </Button>
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
              .map(r => {
                const systemsCheck = systemsChecks[r.phone_e164]
                const isChecking = checkingSystems.has(r.phone_e164)
                
                return (
                <div key={r.id} className="border rounded p-3 space-y-3">
                  {/* Main request info */}
                  <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={!!selected[r.id]} onChange={(e)=>setSelected({...selected, [r.id]: e.target.checked})} />
                  <div className="text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{r.phone_e164} • {r.channel || 'n/a'}</span>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            r.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                            r.status === 'approved' ? 'bg-green-100 text-green-800' :
                            r.status === 'denied' ? 'bg-red-100 text-red-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {r.status.toUpperCase()}
                          </span>
                          {processingRequests.has(r.id) && (
                            <span className="px-2 py-1 rounded text-xs bg-blue-100 text-blue-800 animate-pulse">
                              PROCESSING...
                            </span>
                          )}
                        </div>
                    <div className="text-gray-600">Reason: {r.reason || '—'} • Requested by {(r as any).requested_by?.name || userMap[r.requested_by_user_id]?.name || 'User'}{(r as any).requested_by?.email ? ` (${(r as any).requested_by?.email})` : (userMap[r.requested_by_user_id]?.email ? ` (${userMap[r.requested_by_user_id]?.email})` : '')}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setActiveRequest(r)}>View</Button>
                      <Button 
                        className="bg-green-600 hover:bg-green-700" 
                        onClick={() => setApproveModalFor(r)}
                        disabled={processingRequests.has(r.id)}
                      >
                        {processingRequests.has(r.id) ? 'Processing...' : 'Approve'}
                      </Button>
                      <Button 
                        variant="outline" 
                        onClick={() => setRejectModalFor(r)}
                        disabled={processingRequests.has(r.id)}
                      >
                        {processingRequests.has(r.id) ? 'Processing...' : 'Deny'}
                      </Button>
                    </div>
                  </div>
                  
                  {/* Systems check section */}
                  <div className="border-t pt-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">Systems Check</span>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => checkSystemsForPhone(r.phone_e164)}
                        disabled={isChecking}
                      >
                        {isChecking ? 'Checking...' : systemsCheck ? 'Re-check' : 'Check Systems'}
                      </Button>
                    </div>
                    
                    {systemsCheck ? (
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
                        {/* National DNC */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">National DNC</span>
                          {getStatusBadge(systemsCheck.providers?.dnc?.listed)}
                        </div>
                        
                        {/* RingCentral */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">RingCentral</span>
                          {getStatusBadge(systemsCheck.providers?.ringcentral?.listed)}
                        </div>
                        
                        {/* Convoso */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">Convoso</span>
                          {getStatusBadge(systemsCheck.providers?.convoso?.listed)}
                        </div>
                        
                        {/* Ytel */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">Ytel</span>
                          {getStatusBadge(systemsCheck.providers?.ytel?.listed)}
                        </div>
                        
                        {/* Logics */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">Logics</span>
                          {systemsCheck.providers?.logics ? (
                            systemsCheck.providers.logics.listed ? (
                              <span className="px-1 py-0.5 rounded text-xs bg-blue-100 text-blue-800">Active Case</span>
                            ) : (
                              <span className="px-1 py-0.5 rounded text-xs bg-red-100 text-red-800">No Cases</span>
                            )
                          ) : (
                            <span className="px-1 py-0.5 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                          )}
                          {systemsCheck.providers?.logics?.count && (
                            <span className="text-xs text-gray-600 mt-1">{systemsCheck.providers.logics.count} case(s)</span>
                          )}
                        </div>
                        
                        {/* Genesys */}
                        <div className="flex flex-col items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium text-gray-700">Genesys</span>
                          {getStatusBadge(systemsCheck.providers?.genesys?.listed)}
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500 italic">Click "Check Systems" to see DNC status across all CRM systems</div>
                    )}
                  </div>
                </div>
                )
              })}
            {hasMore && (
              <div className="text-center pt-2">
                <Button variant="outline" onClick={()=>fetchPending(true)}>Load more</Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
    {approveModalFor && (
      <ApproveRequestModal
        phone={approveModalFor.phone_e164}
        requestedBy={userMap[approveModalFor.requested_by_user_id]?.name || userMap[approveModalFor.requested_by_user_id]?.email}
        reason={approveModalFor.reason}
        submitted={approveModalFor.created_at}
        systemsCheckResults={systemsChecks[approveModalFor.phone_e164]}
        onApprove={async (notes, propagateTo) => {
          await act(approveModalFor.id, 'approve', notes, propagateTo)
          setApproveModalFor(null)
        }}
        onCancel={() => setApproveModalFor(null)}
      />
    )}
    {rejectModalFor && (
      <RejectRequestModal
        phone={rejectModalFor.phone_e164}
        onReject={async (notes) => {
          await act(rejectModalFor.id, 'deny', notes)
          setRejectModalFor(null)
        }}
        onCancel={() => setRejectModalFor(null)}
      />
    )}
    {propModal && (
      <PropagationStatusModal
        requestId={propModal.requestId}
        phone={propModal.phone}
        onClose={() => setPropModal(null)}
      />
    )}
    </>
  )
}


