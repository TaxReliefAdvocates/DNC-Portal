import React, { useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Button } from '../ui/button'

type SystemsResult = {
  phone_number: string
  providers: Record<string, any>
}

type PushResult = {
  provider: string
  ok: boolean
  status: number
  body?: any
  at: string
}

const getDemoHeaders = (): Record<string, string> => {
  try {
    const raw = localStorage.getItem('persist:do-not-call-root')
    if (!raw) return {}
    const state = JSON.parse(raw)
    const demoAuth = state.demoAuth ? JSON.parse(state.demoAuth) : null
    if (!demoAuth) return {}
    return {
      'X-Org-Id': String(demoAuth.organizationId),
      'X-User-Id': String(demoAuth.userId),
      'X-Role': String(demoAuth.role),
    }
  } catch {
    return {} as Record<string, string>
  }
}

interface Props { initialPhones?: string[] }

export const AdminSystemsCheck: React.FC<Props> = ({ initialPhones }) => {
  const [phone, setPhone] = useState(initialPhones?.[0] || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SystemsResult | null>(null)
  const [pushing, setPushing] = useState<string | null>(null)
  const [responses, setResponses] = useState<Record<string, PushResult | null>>({})
  const [dncLoading, setDncLoading] = useState(false)
  const [dncError, setDncError] = useState<string | null>(null)
  const [dncFlag, setDncFlag] = useState<boolean | null>(null)
  const [dncRaw, setDncRaw] = useState<any>(null)

  const runCheck = async () => {
    if (!phone.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    // Reset DNC block on new check
    setDncFlag(null); setDncError(null); setDncRaw(null)
    
    const providers: Record<string, any> = {}
    
    try {
      // 1) FreeDNC API check
      try {
        const fj = await fetch(`${API_BASE_URL}/api/check_number`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
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
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
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
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
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
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
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
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
          body: JSON.stringify({ phone_number: phone })
        })
        if (lj.ok) {
          const ljData = await lj.json()
          const cases = ljData?.data?.cases || []
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
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
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

      setResult({ phone_number: phone, providers })
      
      // Also run DNC check, non-blocking
      runDncCheck(phone)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed systems check')
    } finally {
      setLoading(false)
    }
  }

  const cell = (listed?: boolean | null, extra?: string) => {
    if (listed === true) return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Listed</span>
    if (listed === false) return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not listed</span>
    return <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown{extra ? ` • ${extra}` : ''}</span>
  }

  const providers = result?.providers || {}

  const pushRingCentral = async () => {
    if (!result) return
    setPushing('ringcentral')
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ request_id: 0, service_key: 'ringcentral', phone_e164: result.phone_number })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, ringcentral: { provider: 'ringcentral', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushConvoso = async () => {
    if (!result) return
    setPushing('convoso')
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ request_id: 0, service_key: 'convoso', phone_e164: result.phone_number })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, convoso: { provider: 'convoso', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushYtel = async () => {
    if (!result) return
    setPushing('ytel')
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ request_id: 0, service_key: 'ytel', phone_e164: result.phone_number })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, ytel: { provider: 'ytel', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushLogics = async () => {
    if (!result) return
    const firstCaseId = providers.logics?.cases?.[0]?.CaseID
    if (!firstCaseId) return
    setPushing('logics')
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/retry`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ request_id: 0, service_key: 'logics', phone_e164: result.phone_number })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, logics: { provider: 'logics', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushAllRemaining = async () => {
    if (!result) return
    // Fire sequentially to respect simple rate limits
    if (!providers.ringcentral?.listed) await pushRingCentral()
    if (!providers.convoso?.listed) await pushConvoso()
    // Ytel has no read; allow pushing anyway
    await pushYtel()
    if (!providers.logics?.listed) await pushLogics()
  }

  const recheckLogics = async (pn: string) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/logics/search-by-phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: pn })
      })
      if (!resp.ok) return
      const text = await resp.text()
      let data: any = text
      try { data = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, logics_lookup: { provider: 'logics_lookup', ok: true, status: 200, body: data, at: new Date().toISOString() } }))
      setResult((prev)=>{
        if (!prev) return prev
        const cases = Array.isArray(data?.data?.cases) ? data.data.cases : []
        return {
          ...prev,
          providers: {
            ...prev.providers,
            logics: { listed: cases.length>0, count: cases.length, cases }
          }
        }
      })
    } catch {}
  }

  const lookupRingCentral = async (pn?: string) => {
    const num = (pn || phone || '').trim()
    if (!num) return
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/ringcentral/search-dnc`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: num })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, ringcentral_lookup: { provider: 'ringcentral_lookup', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
    } catch {}
  }

  const lookupConvoso = async (pn?: string) => {
    const num = (pn || phone || '').trim()
    if (!num) return
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/convoso/search-dnc`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: num })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, convoso_lookup: { provider: 'convoso_lookup', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
    } catch {}
  }

  const lookupYtel = async (pn?: string) => {
    const num = (pn || phone || '').trim()
    if (!num) return
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/ytel/search-dnc`, { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: num })
      })
      const text = await resp.text()
      let body: any = text
      try { body = JSON.parse(text) } catch {}
      setResponses(prev => ({ ...prev, ytel_lookup: { provider: 'ytel_lookup', ok: resp.ok, status: resp.status, body, at: new Date().toISOString() } }))
    } catch {}
  }

  const runDncCheck = async (pn?: string) => {
    const num = (pn || phone || '').trim()
    if (!num) return
    setDncLoading(true)
    setDncError(null)
    setDncFlag(null)
    setDncRaw(null)
    try {
      const resp = await fetch(`${API_BASE_URL}/api/dnc/check_batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_numbers: [num] })
      })
      const text = await resp.text()
      let data: any = text
      try { data = JSON.parse(text) } catch {}
      setDncRaw(data)
      // Try common shapes
      const first = data?.results?.[0]
      const flag = typeof first?.is_dnc === 'boolean' ? first.is_dnc : (Array.isArray(data?.matches) ? data.matches.length > 0 : null)
      setDncFlag(flag)
    } catch (e) {
      setDncError(e instanceof Error ? e.message : 'Failed DNC check')
    } finally {
      setDncLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Systems Check</CardTitle>
      </CardHeader>
      <CardContent>
        {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
        <div className="flex gap-2 mb-3">
          <Input
            placeholder="Enter phone (any format)"
            value={phone}
            onChange={(e)=>setPhone(e.target.value)}
            onKeyDown={(e)=>{ if (e.key === 'Enter') runCheck() }}
          />
          <Button onClick={runCheck} disabled={loading}>{loading ? 'Checking…' : 'Run Check'}</Button>
        </div>
        {result && (
          <div className="border rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div className="text-sm">
                <span className="font-medium">{result.phone_number}</span>
                {loading && <span className="text-xs text-gray-500"> • Checking…</span>}
              </div>
              <div className="text-xs text-gray-500">{new Date().toLocaleTimeString()}</div>
            </div>
            {loading && (
              <div className="mt-2 h-2 bg-gray-100 rounded overflow-hidden">
                <div className="h-2 w-1/2 bg-blue-200 animate-pulse" />
              </div>
            )}
            <div className="mt-3 space-y-2 text-sm">
              {/* National DNC quick check */}
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">National DNC</div>
                <div className="flex items-center gap-2">
                  {dncLoading ? (
                    <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Checking…</span>
                  ) : dncFlag === true ? (
                    <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Listed</span>
                  ) : dncFlag === false ? (
                    <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not listed</span>
                  ) : (
                    <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                  )}
                  <Button size="sm" variant="outline" onClick={()=>runDncCheck(result.phone_number)} disabled={dncLoading}>Check</Button>
                </div>
              </div>
              {(dncError || dncRaw) && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  {dncError ? (
                    <div className="text-red-600">{dncError}</div>
                  ) : (
                    <>
                      <div className="mb-1">DNC API Response</div>
                      <pre className="whitespace-pre-wrap break-words">{typeof dncRaw === 'string' ? dncRaw : JSON.stringify(dncRaw, null, 2)}</pre>
                    </>
                  )}
                </div>
              )}
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">RingCentral</div>
                <div className="flex items-center gap-2">
                  {cell(providers.ringcentral?.listed)}
                  <Button size="sm" variant="outline" onClick={()=>lookupRingCentral(result.phone_number)}>Lookup</Button>
                  {!providers.ringcentral?.listed && <Button size="sm" variant="outline" onClick={pushRingCentral} disabled={pushing==='ringcentral'}>Push</Button>}
                </div>
              </div>
              {responses.ringcentral_lookup && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Lookup Response ({responses.ringcentral_lookup.status}) • {new Date(responses.ringcentral_lookup.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.ringcentral_lookup.body === 'string' ? responses.ringcentral_lookup.body : JSON.stringify(responses.ringcentral_lookup.body, null, 2)}</pre>
                </div>
              )}
              {responses.ringcentral && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Response ({responses.ringcentral.status}) • {new Date(responses.ringcentral.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.ringcentral.body === 'string' ? responses.ringcentral.body : JSON.stringify(responses.ringcentral.body, null, 2)}</pre>
                </div>
              )}
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Convoso</div>
                <div className="flex items-center gap-2">
                  {cell(providers.convoso?.listed)}
                  <Button size="sm" variant="outline" onClick={()=>lookupConvoso(result.phone_number)}>Lookup</Button>
                  {!providers.convoso?.listed && <Button size="sm" variant="outline" onClick={pushConvoso} disabled={pushing==='convoso'}>Push</Button>}
                </div>
              </div>
              {responses.convoso_lookup && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Lookup Response ({responses.convoso_lookup.status}) • {new Date(responses.convoso_lookup.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.convoso_lookup.body === 'string' ? responses.convoso_lookup.body : JSON.stringify(responses.convoso_lookup.body, null, 2)}</pre>
                </div>
              )}
              {responses.convoso && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Response ({responses.convoso.status}) • {new Date(responses.convoso.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.convoso.body === 'string' ? responses.convoso.body : JSON.stringify(responses.convoso.body, null, 2)}</pre>
                </div>
              )}
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Logics (TPS)</div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2">
                    {providers.logics ? (
                      providers.logics.listed ? (
                        <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">True</span>
                      ) : (
                        <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">False</span>
                      )
                    ) : (
                      <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                    )}
                    {typeof providers.logics?.count === 'number' && (
                      <span className="text-xs text-gray-600">{providers.logics.count} case(s)</span>
                    )}
                  </div>
                  <Button size="sm" variant="outline" onClick={()=>recheckLogics(result.phone_number)}>Lookup</Button>
                  {providers.logics?.cases?.[0]?.CaseID && <Button size="sm" variant="outline" onClick={pushLogics} disabled={pushing==='logics'}>Push</Button>}
                </div>
              </div>
              {responses.logics_lookup && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Lookup Response ({responses.logics_lookup.status}) • {new Date(responses.logics_lookup.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.logics_lookup.body === 'string' ? responses.logics_lookup.body : JSON.stringify(responses.logics_lookup.body, null, 2)}</pre>
                </div>
              )}
              {responses.logics && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Response ({responses.logics.status}) • {new Date(responses.logics.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.logics.body === 'string' ? responses.logics.body : JSON.stringify(responses.logics.body, null, 2)}</pre>
                </div>
              )}
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Ytel</div>
                <div className="flex items-center gap-2">
                  {cell(providers.ytel?.listed)}
                  <Button size="sm" variant="outline" onClick={()=>lookupYtel(result.phone_number)}>Lookup</Button>
                  <Button size="sm" variant="outline" onClick={pushYtel} disabled={pushing==='ytel'}>Push</Button>
                </div>
              </div>
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Genesys</div>
                <div className="flex items-center gap-2">
                  {cell(providers.genesys?.listed)}
                  <Button size="sm" variant="outline" onClick={()=>{}} disabled>Lookup</Button>
                  <Button size="sm" variant="outline" onClick={()=>{}} disabled>Push</Button>
                </div>
              </div>
              {responses.ytel_lookup && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Lookup Response ({responses.ytel_lookup.status}) • {new Date(responses.ytel_lookup.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.ytel_lookup.body === 'string' ? responses.ytel_lookup.body : JSON.stringify(responses.ytel_lookup.body, null, 2)}</pre>
                </div>
              )}
              {responses.ytel && (
                <div className="text-xs text-gray-700 border rounded p-2 bg-gray-50">
                  <div className="mb-1">Response ({responses.ytel.status}) • {new Date(responses.ytel.at).toLocaleTimeString()}</div>
                  <pre className="whitespace-pre-wrap break-words">{typeof responses.ytel.body === 'string' ? responses.ytel.body : JSON.stringify(responses.ytel.body, null, 2)}</pre>
                </div>
              )}
            </div>
            <div className="mt-3">
              <Button onClick={pushAllRemaining} disabled={pushing!==null}>Push DNC to remaining</Button>
            </div>
            <div className="mt-3 text-xs text-gray-600 space-y-1">
              <div><strong>Current behavior:</strong></div>
              <div>• RingCentral: search blocked list; "Listed" if found on DNC.</div>
              <div>• Convoso: search DNC leads; "Listed" if found on DNC.</div>
              <div>• Logics (TPS): search cases by phone; "Listed" if cases found.</div>
              <div>• Ytel: two-step DNC check; "Listed" if on DNC or global DNC.</div>
              <div>• Genesys: search DNC list; "Listed" if found on DNC.</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}


