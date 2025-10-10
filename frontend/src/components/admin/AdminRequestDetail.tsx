import { API_BASE_URL, apiCall } from '@/lib/api'
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

export const AdminRequestDetail: React.FC<Props> = ({ request, onBack }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [systemsCheck, setSystemsCheck] = useState<any | null>(null)
  const [logicsCases, setLogicsCases] = useState<any[]>([])
  const [notes, setNotes] = useState('')
  const [isApproving, setIsApproving] = useState(false)
  const [approvalProgress, setApprovalProgress] = useState<Record<string, 'pending' | 'loading' | 'success' | 'error'>>({})
  const [approvalSuccess, setApprovalSuccess] = useState(false)


  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true)
      setError(null)
      try {
        // Fetch Systems Check results (same as Systems Check pane)
        const systemsCheckData: Record<string, any> = {}
        
        // 1) FreeDNC API check
        try {
          const fjData = await apiCall(`${API_BASE_URL}/api/check_number`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          systemsCheckData.dnc = { listed: Boolean(fjData?.is_dnc) }
        } catch {}

        // 2) RingCentral search
        try {
          const rj = await apiCall(`${API_BASE_URL}/api/v1/ringcentral/search-dnc`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          const isOnDnc = rj?.data?.is_on_dnc
          if (isOnDnc === null) {
            systemsCheckData.ringcentral = { listed: null, status: 'unknown' }
          } else {
            systemsCheckData.ringcentral = { listed: isOnDnc || false }
          }
        } catch {}

        // 3) Convoso search
        try {
          const cj = await apiCall(`${API_BASE_URL}/api/v1/convoso/search-dnc`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          const isOnDnc = cj?.data?.is_on_dnc
          if (isOnDnc === null) {
            systemsCheckData.convoso = { listed: null, status: 'unknown' }
          } else {
            systemsCheckData.convoso = { listed: isOnDnc || false }
          }
        } catch {}

        // 4) Ytel search
        try {
          const yj = await apiCall(`${API_BASE_URL}/api/v1/ytel/search-dnc`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          const isOnDnc = yj?.data?.is_on_dnc
          if (isOnDnc === null) {
            systemsCheckData.ytel = { listed: null, status: 'unknown' }
          } else {
            systemsCheckData.ytel = { listed: isOnDnc || false }
          }
        } catch {}

        // 5) Logics search (for cases)
        try {
          const ljData = await apiCall(`${API_BASE_URL}/api/v1/logics/search-by-phone`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          const cases = ljData?.data?.raw_response?.Data || []
          systemsCheckData.logics = { 
            listed: cases.length > 0, 
            count: cases.length, 
            cases: cases 
          }
          setLogicsCases(cases)
        } catch {}

        // 6) Genesys search
        try {
          const gjData = await apiCall(`${API_BASE_URL}/api/v1/genesys/search-dnc`, { 
            method:'POST', 
            body: JSON.stringify({ phone_number: request.phone_e164 })
          })
          const isOnDnc = gjData?.data?.is_on_dnc
          if (isOnDnc === null) {
            systemsCheckData.genesys = { listed: null, status: 'unknown' }
          } else {
            systemsCheckData.genesys = { listed: isOnDnc || false }
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
    if (action === 'approve') {
      setIsApproving(true)
      setError(null)
      setApprovalSuccess(false)
      
      // Initialize progress tracking for each system
      const systems = ['RingCentral', 'Convoso', 'Ytel', 'Genesys', 'Logics', 'DNC History']
      const initialProgress: Record<string, 'pending' | 'loading' | 'success' | 'error'> = {}
      systems.forEach(system => {
        initialProgress[system] = 'pending'
      })
      setApprovalProgress(initialProgress)
      
      try {
        // Step 1: Approve the request
        setApprovalProgress(prev => ({ ...prev, 'DNC History': 'loading' }))
        await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${request.id}/decide`, { 
          method:'PATCH', 
          body: JSON.stringify({ decision: 'approved', notes }) 
        })
        
        setApprovalProgress(prev => ({ ...prev, 'DNC History': 'success' }))
        
        // Step 2: Poll real propagation status until completion
        const toKey: Record<string,string> = { ringcentral: 'RingCentral', convoso: 'Convoso', ytel: 'Ytel', genesys: 'Genesys', logics: 'Logics' }
        let done = false
        const start = Date.now()
        while (!done && Date.now() - start < 120000) { // up to 2 minutes
          try {
            const st = await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${request.id}/status`, { method:'GET' })
            const attempts: Array<{service_key:string,status:string}> = st?.attempts || []
            // Update UI per provider
            const next = { ...initialProgress }
            attempts.forEach(a => {
              const label = toKey[a.service_key]
              if (!label) return
              if (a.status === 'pending' || a.status === 'in_progress') next[label] = 'loading'
              else if (a.status === 'success' || a.status === 'skipped') next[label] = 'success'
              else next[label] = 'error'
            })
            setApprovalProgress(next)
            // Check completion
            done = attempts.length > 0 && attempts.every(a => ['success','failed','skipped'].includes(a.status))
            if (done) break
          } catch {}
          await new Promise(r => setTimeout(r, 1000))
        }
        setApprovalSuccess(true)
        
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Approval failed')
        setApprovalProgress(prev => {
          const newProgress = { ...prev }
          Object.keys(newProgress).forEach(key => {
            if (newProgress[key] === 'loading') {
              newProgress[key] = 'error'
            }
          })
          return newProgress
        })
      } finally {
        setIsApproving(false)
      }
    } else {
      // Deny action (simpler)
      try {
        await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${request.id}/deny`, { 
          method:'POST', 
          body: JSON.stringify({ notes }) 
        })
      onBack()
    } catch (e) {
        setError(e instanceof Error ? e.message : 'Denial failed')
      }
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
                
                {/* Logics */}
                <div className="flex items-center justify-between border rounded p-2">
                  <div className="font-medium">Logics</div>
                  <div className="flex items-center gap-2">
                    {systemsCheck.providers?.logics?.listed ? (
                      <span className="px-2 py-1 rounded text-xs bg-blue-100 text-blue-800 font-medium">
                        Active Case ({systemsCheck.providers.logics.count} case{systemsCheck.providers.logics.count !== 1 ? 's' : ''})
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">No Cases</span>
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
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Logics Cases
              {logicsCases.length > 0 && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full font-medium">
                  {logicsCases.length} Active Case{logicsCases.length !== 1 ? 's' : ''}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? 'Loading…' : logicsCases.length ? (
              <div className="space-y-3">
                {logicsCases.map((c:any,idx:number)=> (
                  <div key={idx} className="border border-blue-200 rounded-lg p-3 bg-blue-50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-blue-600 text-white text-xs rounded font-medium">
                          ACTIVE CASE
                        </span>
                        <span className="font-semibold text-blue-900">Case #{c.CaseID}</span>
                      </div>
                      <a
                        href={`https://tps.logiqs.com/Cases/Case.aspx?CaseID=${c.CaseID}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors"
                      >
                        View in Logics →
                      </a>
                    </div>
                    
                    <div className="grid grid-cols-1 gap-2 text-sm">
                      <div>
                        <span className="font-medium text-gray-700">Name:</span>
                        <span className="ml-1 text-gray-900">
                          {[c.FirstName, c.MiddleName, c.LastName]
                            .filter(Boolean)
                            .join(' ') || 'N/A'}
                        </span>
                      </div>
                      {c.Email && (
                        <div>
                          <span className="font-medium text-gray-700">Email:</span>
                          <span className="ml-1 text-gray-900">{c.Email}</span>
                        </div>
                      )}
                      {c.CreatedDate && (
                        <div>
                          <span className="font-medium text-gray-700">Created:</span>
                          <span className="ml-1 text-gray-900">{new Date(c.CreatedDate).toLocaleString()}</span>
                        </div>
                      )}
                      {c.TaxAmount && (
                        <div>
                          <span className="font-medium text-gray-700">Tax Amount:</span>
                          <span className="ml-1 text-gray-900">${c.TaxAmount.toLocaleString()}</span>
                        </div>
                      )}
                      {c.StatusID && (
                    <div>
                          <span className="font-medium text-gray-700">Status ID:</span>
                          <span className="ml-1 text-gray-900">{c.StatusID}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-600 text-sm text-center py-4">
                <div className="text-gray-400 mb-2">📋</div>
                No Logics cases found
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Decision</CardTitle></CardHeader>
        <CardContent>
          {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
          
          {approvalSuccess && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center gap-2 text-green-800">
                <span className="text-lg">✅</span>
                <span className="font-medium">Request approved successfully!</span>
              </div>
              <div className="text-sm text-green-700 mt-1">
                Number has been added to DNC lists and will appear in DNC History. This window will close automatically.
              </div>
            </div>
          )}
          
          {isApproving && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-2 text-blue-800 mb-3">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span className="font-medium">Approving request and pushing to systems...</span>
              </div>
              
              <div className="space-y-2">
                {Object.entries(approvalProgress).map(([system, status]) => (
                  <div key={system} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{system}</span>
                    <div className="flex items-center gap-2">
                      {status === 'pending' && (
                        <span className="text-gray-400">⏳ Pending</span>
                      )}
                      {status === 'loading' && (
                        <span className="text-blue-600">🔄 Processing...</span>
                      )}
                      {status === 'success' && (
                        <span className="text-green-600">✅ Success</span>
                      )}
                      {status === 'error' && (
                        <span className="text-red-600">❌ Failed</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="flex items-center gap-2">
            <Input 
              placeholder="Decision notes (optional)" 
              value={notes} 
              onChange={(e)=>setNotes(e.target.value)}
              disabled={isApproving}
            />
            <Button 
              onClick={()=>act('approve')} 
              className="bg-green-600 hover:bg-green-700"
              disabled={isApproving}
            >
              {isApproving ? 'Approving...' : 'Approve'}
            </Button>
            <Button 
              variant="outline" 
              onClick={()=>act('deny')}
              disabled={isApproving}
            >
              Deny
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}


