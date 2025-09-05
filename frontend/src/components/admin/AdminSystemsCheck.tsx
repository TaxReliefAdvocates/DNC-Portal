import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Button } from '../ui/button'

type SystemsResult = {
  phone_number: string
  providers: Record<string, any>
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

  const runCheck = async () => {
    if (!phone.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/systems-check?phone_number=${encodeURIComponent(phone.trim())}`, { headers: { 'Content-Type': 'application/json', ...getDemoHeaders() } })
      if (!resp.ok) throw new Error('Failed systems check')
      const data = await resp.json()
      setResult(data)
      // Enrich Logics (TPS) with direct case lookup to ensure accuracy
      await recheckLogics(data.phone_number)
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
      await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ringcentral/block?phone_number=${encodeURIComponent(result.phone_number)}`, { method:'POST', headers: { ...getDemoHeaders() } })
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushConvoso = async () => {
    if (!result) return
    setPushing('convoso')
    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/convoso/dnc/insert?phone_number=${encodeURIComponent(result.phone_number)}`, { method:'POST', headers: { ...getDemoHeaders() } })
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushYtel = async () => {
    if (!result) return
    setPushing('ytel')
    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ytel/dnc?phone_number=${encodeURIComponent(result.phone_number)}`, { method:'POST', headers: { ...getDemoHeaders() } })
      await runCheck()
    } finally { setPushing(null) }
  }

  const pushLogics = async () => {
    if (!result) return
    const firstCaseId = providers.logics?.cases?.[0]?.CaseID
    if (!firstCaseId) return
    setPushing('logics')
    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/logics/dnc/update-case?case_id=${encodeURIComponent(firstCaseId)}&status_id=2`, { method:'POST', headers: { ...getDemoHeaders() } })
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
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: pn })
      })
      if (!resp.ok) return
      const data = await resp.json()
      setResult((prev)=>{
        if (!prev) return prev
        const cases = Array.isArray(data.cases) ? data.cases : []
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
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">RingCentral</div>
                <div className="flex items-center gap-2">
                  {cell(providers.ringcentral?.listed)}
                  {!providers.ringcentral?.listed && <Button size="sm" variant="outline" onClick={pushRingCentral} disabled={pushing==='ringcentral'}>Push</Button>}
                </div>
              </div>
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Convoso</div>
                <div className="flex items-center gap-2">
                  {cell(providers.convoso?.listed)}
                  {!providers.convoso?.listed && <Button size="sm" variant="outline" onClick={pushConvoso} disabled={pushing==='convoso'}>Push</Button>}
                </div>
              </div>
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
                  {providers.logics?.cases?.[0]?.CaseID && <Button size="sm" variant="outline" onClick={pushLogics} disabled={pushing==='logics'}>Push</Button>}
                </div>
              </div>
              <div className="flex items-center justify-between border rounded p-2">
                <div className="font-medium">Ytel</div>
                <div className="flex items-center gap-2">
                  {cell(providers.ytel?.listed, 'read N/A')}
                  <Button size="sm" variant="outline" onClick={pushYtel} disabled={pushing==='ytel'}>Push</Button>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <Button onClick={pushAllRemaining} disabled={pushing!==null}>Push DNC to remaining</Button>
            </div>
            <div className="mt-3 text-xs text-gray-600 space-y-1">
              <div><strong>Current behavior:</strong></div>
              <div>• RingCentral: paginated blocked list search; “Listed” if found.</div>
              <div>• Convoso: DNC search; “Listed” if found.</div>
              <div>• Logics (TPS): “Listed” when cases are found by phone (count and first few returned).</div>
              <div>• Ytel: no read API; shows “Unknown”.</div>
              <div>• Genesys: placeholder for now.</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}


