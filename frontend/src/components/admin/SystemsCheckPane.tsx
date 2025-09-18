import React, { useEffect, useState } from 'react'
import { API_BASE_URL } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
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

interface Props { numbers: string[], onAutomationComplete?: (total: number) => void }

export const SystemsCheckPane: React.FC<Props> = ({ numbers, onAutomationComplete }) => {
  const [results, setResults] = useState<Record<string, SystemsResult>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [, setErr] = useState<string | null>(null)
  const [pushing, setPushing] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [progress, setProgress] = useState<{ total: number, completed: number, failed: number, per: Record<string, { completed: number, failed: number }>, logs: string[] }>({ total: 0, completed: 0, failed: 0, per: { ringcentral: { completed: 0, failed: 0 }, convoso: { completed: 0, failed: 0 }, ytel: { completed: 0, failed: 0 }, logics: { completed: 0, failed: 0 } }, logs: [] })

  const runCheck = async (phone: string) => {
    setLoading((s)=>({ ...s, [phone]: true }))
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/systems-check?phone_number=${encodeURIComponent(phone)}`, { headers: { ...getDemoHeaders() } })
      if (resp.ok) {
        const data = await resp.json()
        setResults((r)=>({ ...r, [phone]: data }))
        setErr(null)
        // Ensure Logics (TPS) detection by doing a direct case lookup
        await recheckLogics(phone)
      } else {
        setErr('Backend request failed')
      }
    } catch (e) {
      setErr('Cannot reach backend (check that it is running)')
    } finally {
      setLoading((s)=>({ ...s, [phone]: false }))
    }
  }

  useEffect(()=>{
    numbers.forEach((n)=> runCheck(n))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numbers.join(',')])

  const cell = (listed?: boolean | null, extra?: string) => {
    if (listed === true) return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Listed</span>
    if (listed === false) return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not listed</span>
    return <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown{extra ? ` • ${extra}` : ''}</span>
  }

  const push = async (provider: 'ringcentral'|'convoso'|'ytel'|'logics', phone: string) => {
    setPushing(`${provider}:${phone}`)
    try {
      // record attempt start
      try {
        await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/attempt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
          body: JSON.stringify({ organization_id: 1, service_key: provider, phone_e164: phone, status: 'pending', attempt_no: 1 })
        })
      } catch {}
      if (provider === 'ringcentral') {
        await fetch(`${API_BASE_URL}/api/v1/ringcentral/dnc/add?phone_number=${encodeURIComponent(phone)}&label=${encodeURIComponent('API Block')}`, { method:'POST', headers: { ...getDemoHeaders() } })
      } else if (provider === 'convoso') {
        await fetch(`${API_BASE_URL}/api/v1/convoso/dnc/add?phone_number=${encodeURIComponent(phone)}`, { method:'POST', headers: { ...getDemoHeaders() } })
      } else if (provider === 'ytel') {
        await fetch(`${API_BASE_URL}/api/v1/ytel/dnc/add?phone_number=${encodeURIComponent(phone)}`, { method:'POST', headers: { ...getDemoHeaders() } })
      } else if (provider === 'logics') {
        const res = results[phone]
        const firstCaseId = res?.providers?.logics?.cases?.[0]?.CaseID
        if (firstCaseId) {
          await fetch(`${API_BASE_URL}/api/v1/logics/dnc/update-case?case_id=${encodeURIComponent(firstCaseId)}&status_id=2`, { method:'POST', headers: { ...getDemoHeaders() } })
        }
      }
      await runCheck(phone)
      setProgress((p)=>({
        ...p,
        completed: p.completed + 1,
        per: { ...p.per, [provider]: { ...p.per[provider], completed: p.per[provider].completed + 1 } },
        logs: [...p.logs, `${provider} ✓ ${phone}`].slice(-200)
      }))
      try {
        await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/attempt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
          body: JSON.stringify({ organization_id: 1, service_key: provider, phone_e164: phone, status: 'success', attempt_no: 1 })
        })
      } catch {}
    } catch (e) {
      setProgress((p)=>({
        ...p,
        failed: p.failed + 1,
        per: { ...p.per, [provider]: { ...p.per[provider], failed: p.per[provider].failed + 1 } },
        logs: [...p.logs, `${provider} ✗ ${phone} ${(e as Error)?.message || ''}`].slice(-200)
      }))
      try {
        await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/attempt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
          body: JSON.stringify({ organization_id: 1, service_key: provider, phone_e164: phone, status: 'failed', error_message: (e as Error)?.message || 'failed', attempt_no: 1 })
        })
      } catch {}
    } finally { setPushing(null) }
  }

  const recheckLogics = async (phone: string) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: phone })
      })
      if (!resp.ok) return
      const data = await resp.json()
      setResults((r)=>{
        const prev = r[phone] || { phone_number: phone, providers: {} as any }
        const cases = Array.isArray(data.cases) ? data.cases : []
        return { ...r, [phone]: { ...prev, providers: { ...prev.providers, logics: { listed: cases.length>0, count: cases.length, cases } } } }
      })
    } catch {}
  }

  return (
    <>
    <Card>
      <CardHeader>
        <CardTitle>Systems Check Results</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {numbers.map((n)=>{
            const res = results[n]
            const providers = res?.providers || {}
            return (
              <div key={n} className="border rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm">
                    <span className="font-medium">{n}</span>
                    {loading[n] && <span className="text-xs text-gray-500"> • Checking…</span>}
                  </div>
                  <div className="text-xs text-gray-500">{new Date().toLocaleTimeString()}</div>
                </div>
                {loading[n] && (
                  <div className="mt-2 h-2 bg-gray-100 rounded overflow-hidden">
                    <div className="h-2 w-1/2 bg-blue-200 animate-pulse" />
                  </div>
                )}
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                  <div className="flex items-center justify-between border rounded p-2">
                    <div className="font-medium">DNC (Federal)</div>
                    <div className="flex items-center gap-2">
                      {providers.dnc ? (
                        providers.dnc.listed ? (
                          <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
                        ) : (
                          <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not on DNC</span>
                        )
                      ) : (
                        <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Checking…</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center justify-between border rounded p-2">
                    <div className="font-medium">RingCentral</div>
                    <div className="flex items-center gap-2">
                      {cell(providers.ringcentral?.listed)}
                      {!providers.ringcentral?.listed && <Button size="sm" variant="outline" onClick={()=>push('ringcentral', n)} disabled={pushing===`ringcentral:${n}`}>Push</Button>}
                    </div>
                  </div>
                  <div className="flex items-center justify-between border rounded p-2">
                    <div className="font-medium">Convoso</div>
                    <div className="flex items-center gap-2">
                      {cell(providers.convoso?.listed)}
                      {!providers.convoso?.listed && <Button size="sm" variant="outline" onClick={()=>push('convoso', n)} disabled={pushing===`convoso:${n}`}>Push</Button>}
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
                      {providers.logics?.cases?.[0]?.CaseID && <Button size="sm" variant="outline" onClick={()=>push('logics', n)} disabled={pushing===`logics:${n}`}>Push</Button>}
                    </div>
                  </div>
                  <div className="flex items-center justify-between border rounded p-2">
                    <div className="font-medium">Ytel</div>
                    <div className="flex items-center gap-2">
                      {cell(providers.ytel?.listed, 'read N/A')}
                      <Button size="sm" variant="outline" onClick={()=>push('ytel', n)} disabled={pushing===`ytel:${n}`}>Push</Button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        {/* close container above */}
      </CardContent>
    </Card>
    <div className="mt-3 flex justify-end">
      <Button
        onClick={async ()=>{
          try {
            const tasks: { provider: 'ringcentral'|'convoso'|'ytel'|'logics', phone: string }[] = []
            numbers.forEach((n)=>{
              const res = results[n]
              const prov = res?.providers || {}
              if (!prov.ringcentral?.listed) tasks.push({ provider:'ringcentral', phone: n })
              if (!prov.convoso?.listed) tasks.push({ provider:'convoso', phone: n })
              tasks.push({ provider:'ytel', phone: n })
              if (prov.logics?.cases?.[0]?.CaseID) tasks.push({ provider:'logics', phone: n })
            })

            setProgress({
              total: tasks.length,
              completed: 0,
              failed: 0,
              per: { ringcentral: { completed: 0, failed: 0 }, convoso: { completed: 0, failed: 0 }, ytel: { completed: 0, failed: 0 }, logics: { completed: 0, failed: 0 } },
              logs: [],
            })
            setShowModal(true)
            for (const t of tasks) {
              // eslint-disable-next-line no-await-in-loop
              await push(t.provider, t.phone)
            }
          } finally {
            // keep modal open until explicit close
            onAutomationComplete?.(progress.total)
          }
        }}
        disabled={pushing !== null}
      >
        Put on DNC List (all remaining)
      </Button>
    </div>
    {showModal && (
      <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center">
        <div className="bg-white rounded shadow-lg w-full max-w-2xl p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-lg font-semibold">Push Progress</div>
            <button className="text-sm text-gray-600" onClick={()=>setShowModal(false)}>Close</button>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-2 border rounded">
              <div className="font-medium mb-1">Overall</div>
              <div>Completed: {progress.completed} / {progress.total}</div>
              <div>Failed: {progress.failed}</div>
              <div className="mt-2 h-2 bg-gray-200 rounded overflow-hidden">
                <div className="h-2 bg-blue-600" style={{ width: `${Math.min(100, (progress.completed / Math.max(1, progress.total)) * 100)}%` }} />
              </div>
            </div>
            <div className="p-2 border rounded">
              <div className="font-medium mb-1">By Provider</div>
              {(['ringcentral','convoso','ytel','logics'] as const).map((k)=> (
                <div key={k} className="flex items-center justify-between">
                  <span className="capitalize">{k}</span>
                  <span>{progress.per[k].completed} ✓ / {progress.per[k].failed} ✗</span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 max-h-40 overflow-y-auto text-xs bg-gray-50 border rounded p-2">
            {progress.logs.map((l, i)=> (<div key={i}>{l}</div>))}
          </div>
        </div>
      </div>
    )}
    </>
  )
}


