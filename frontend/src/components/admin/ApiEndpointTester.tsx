import React, { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { API_BASE_URL } from '@/lib/api'

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

type Endpoint = {
  id: string
  name: string
  url: string
  method: Method
  tags: string[]
  description?: string
  requestBodyExample?: any
  headers?: Record<string, string>
  prereqs?: Endpoint[]
  hasBody?: boolean
}

type StepResult = { title: string; ok: boolean; status: number; ms: number; body: any }
type TestResult = { id: string; ok: boolean; totalMs: number; steps: StepResult[]; when: string }

const groupBy = (arr: Endpoint[], key: (e: Endpoint)=>string) => {
  const m: Record<string, Endpoint[]> = {}
  arr.forEach(e => { const k = key(e); if (!m[k]) m[k]=[]; m[k].push(e) })
  return m
}

const methodOf = (k: string): Method | null => {
  const u = k.toUpperCase()
  return (['GET','POST','PUT','DELETE','PATCH'] as Method[]).includes(u as Method) ? (u as Method) : null
}

export const ApiEndpointTester: React.FC = () => {
  const [testValue, setTestValue] = useState('5618189087')
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [results, setResults] = useState<Record<string, TestResult>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [syncing, setSyncing] = useState(false)
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [specBaseUrl, setSpecBaseUrl] = useState<string | undefined>(undefined)
  const [customBodies, setCustomBodies] = useState<Record<string, string>>({})
  const [customParams, setCustomParams] = useState<Record<string, Record<string,string>>>({})

  const substitutePathParams = (path: string) => path.replace(/\{[^/}]+\}/g, encodeURIComponent(testValue || ''))

  const groups = useMemo(()=> groupBy(endpoints, e=> (e.tags && e.tags[0]) || e.url.split('/').slice(0,4).join('/') || 'Untagged'), [endpoints])

  const syncFromOpenAPI = async () => {
    setSyncing(true); setSyncError(null)
    try {
      const resp = await fetch(`${API_BASE_URL}/openapi.json`)
      if (!resp.ok) throw new Error(`OpenAPI fetch failed: ${resp.status}`)
      const spec = await resp.json()
      const baseUrl: string | undefined = (spec.servers && spec.servers[0]?.url) || undefined
      setSpecBaseUrl(baseUrl)
      const out: Endpoint[] = []
      const paths = spec.paths || {}
      Object.entries(paths).forEach(([path, ops]: any) => {
        Object.entries(ops || {}).forEach(([verb, op]: any) => {
          const m = methodOf(verb)
          if (!m) return
          const id = `${m}-${path}`
          // Append query parameter placeholders based on OpenAPI parameter list
          const params = Array.isArray(op?.parameters) ? (op.parameters as any[]).filter(p => p?.in === 'query').map(p => p?.name).filter(Boolean) : []
          const querySuffix = params.length ? `?${params.map((n:string)=>`${n}={${n}}`).join('&')}` : ''
          const url = `${path}${querySuffix}`
          const name = op?.summary || `${m} ${path}`
          const tags: string[] = Array.isArray(op?.tags) ? op.tags : ['Untagged']
          let example: any = undefined
          try {
            example = op?.requestBody?.content?.['application/json']?.example
              || op?.requestBody?.content?.['application/json']?.examples?.[0]
          } catch {}
          const hasBody = !!op?.requestBody
          // Heuristic prereq for RingCentral auth (new provider endpoints)
          const prereqs: Endpoint[] = url.includes('/ringcentral/') && !url.includes('/auth')
            ? [{ id:'rc-auth', name:'RingCentral Auth', url: '/api/ringcentral/auth', method:'POST', tags:['RingCentral'] }]
            : []
          const headers = hasBody ? { 'Content-Type': 'application/json' } : undefined
          out.push({ id, name, url, method: m, tags, description: op?.description, requestBodyExample: example, headers, prereqs, hasBody })
        })
      })
      // Append curated provider endpoints to guarantee coverage and correct request bodies
  const curated = buildProviderEndpoints().filter(e => !/^POST|GET|DELETE/.test('') )
      const seen = new Set(out.map(e => e.id))
      const merged = [...out]
      curated.forEach(e => { if (!seen.has(e.id)) { merged.push(e); seen.add(e.id) } })
      setEndpoints(merged)
      setLastSync(new Date().toISOString())
    } catch (e:any) {
      setSyncError(e?.message || String(e))
    } finally { setSyncing(false) }
  }

  useEffect(()=>{ syncFromOpenAPI() }, [])

  const buildUrl = (pathOrUrl: string): string => {
    if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl
    const base = specBaseUrl && /^https?:\/\//i.test(specBaseUrl) ? specBaseUrl : API_BASE_URL
    const baseClean = base.replace(/\/$/, '')
    const pathClean = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
    // Replace path params
    const substituted = pathClean.replace(/\{[^/}]+\}/g, encodeURIComponent(testValue || ''))
    return `${baseClean}${substituted}`
  }

  const runStep = async (title: string, method: Method, urlOrPath: string, headers?: Record<string,string>, body?: any): Promise<StepResult> => {
    const started = performance.now()
    try {
      // prefer custom JSON body if provided for write methods
      let resolvedBody: any = body
      if (['POST','PUT','PATCH'].includes(method)) {
        const custom = customBodies[urlOrPath]
        if (custom && custom.trim().length) {
          try { resolvedBody = JSON.parse(custom) } catch { /* ignore parse error, fall back to default */ }
        }
      }
      const payload = resolvedBody !== undefined ? (typeof resolvedBody === 'string' ? resolvedBody : JSON.stringify(resolveBodyPlaceholders(resolvedBody))) : undefined
      const resp = await fetch(buildUrl(applyQueryOverrides(urlOrPath)), { method, headers, body: payload })
      const txt = await resp.text()
      let data: any = txt
      try { data = JSON.parse(txt) } catch {}
      return { title, ok: resp.ok, status: resp.status, ms: Math.round(performance.now()-started), body: data }
    } catch (e:any) {
      return { title, ok: false, status: 0, ms: Math.round(performance.now()-started), body: String(e?.message||e) }
    }
  }
  // Parse initial query params from a path like /api/foo?x=1&y=2
  const parseQueryParams = (path: string): string[] => {
    const qIndex = path.indexOf('?')
    if (qIndex === -1) return []
    const qs = path.slice(qIndex+1)
    return qs.split('&').map(p => p.split('=')[0]).filter(Boolean)
  }

  // Apply overrides from customParams into the path's query string
  const applyQueryOverrides = (path: string): string => {
    const overrides = customParams[path]
    if (!overrides || Object.keys(overrides).length === 0) return path
    const qIndex = path.indexOf('?')
    const base = qIndex === -1 ? path : path.slice(0, qIndex)
    const urlSearch = new URLSearchParams(qIndex === -1 ? '' : path.slice(qIndex+1))
    Object.entries(overrides).forEach(([k,v]) => {
      if (v === undefined || v === null || String(v).trim() === '') return
      urlSearch.set(k, String(v))
    })
    const qs = urlSearch.toString()
    return qs ? `${base}?${qs}` : base
  }


  const testEndpoint = async (ep: Endpoint) => {
    setLoading(prev => ({ ...prev, [ep.id]: true }))
    const steps: StepResult[] = []
    const t0 = performance.now()
    // prereqs (e.g., OAuth)
    if (ep.prereqs && ep.prereqs.length) {
      for (const pre of ep.prereqs) {
        const url = substitutePathParams(pre.url || '') || substitutePathParams(ep.url)
        const s = await runStep(pre.name || 'OAuth / Prereq', pre.method || 'GET', url, pre.headers)
        steps.push(s)
        if (!s.ok) break
      }
    }
    if (steps.every(s=> s.ok)) {
      const url = substitutePathParams(ep.url)
      const s = await runStep('API Call', ep.method, url, ep.headers, ep.hasBody ? ep.requestBodyExample : undefined)
      steps.push(s)
    }
    const totalMs = Math.round(performance.now()-t0)
    const ok = steps.length>0 && steps.every(s=> s.ok)
    const res: TestResult = { id: ep.id, ok, totalMs, steps, when: new Date().toISOString() }
    setResults(prev => ({ ...prev, [ep.id]: res }))
    setLoading(prev => ({ ...prev, [ep.id]: false }))
  }

  const badge = (m: Method) => (
    <span className={`px-2 py-0.5 text-xs rounded ${m==='GET'?'bg-green-100 text-green-800': m==='POST'?'bg-blue-100 text-blue-800': m==='PUT'?'bg-yellow-100 text-yellow-800': m==='DELETE'?'bg-red-100 text-red-800':'bg-gray-100 text-gray-700'}`}>{m}</span>
  )

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>API Endpoint Tester</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
            <div className="md:col-span-2">
              <label className="text-sm text-gray-700">Test Value (replaces path parameters in URLs)</label>
              <Input value={testValue} onChange={(e)=>setTestValue(e.target.value)} placeholder="5618189087" />
            </div>
            <div className="flex items-end gap-2">
              <Button className="bg-green-600 hover:bg-green-700" onClick={syncFromOpenAPI} disabled={syncing}>{syncing ? 'Syncing…' : 'Sync with OpenAPI'}</Button>
              <div className="text-xs text-gray-600">{lastSync ? `Last synced: ${new Date(lastSync).toLocaleTimeString()} • ${endpoints.length} endpoints` : 'Not synced yet'}</div>
            </div>
          </div>
          {syncError && <div className="text-sm text-red-600 mt-2">{syncError}</div>}
        </CardContent>
      </Card>

      {Object.entries(groups).map(([group, list]) => (
        <div key={group} className="space-y-2">
          <div className="text-sm text-gray-600 font-semibold">{group} • {list.length}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {list.map(ep => {
              const r = results[ep.id]
              const isWrite = ['POST','PUT','PATCH'].includes(ep.method)
              const hasQuery = ep.url.includes('?')
              const defaultBody = JSON.stringify(resolveBodyPlaceholders(ep.requestBodyExample ?? { phoneNumber: '{phoneNumber}' }), null, 2)
              return (
                <Card key={ep.id}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between text-base">
                      <span>{ep.name}</span>
                      {badge(ep.method)}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {ep.description && <div className="text-sm text-gray-600 mb-2">{ep.description}</div>}
                    <div className="text-xs font-mono break-all bg-gray-50 border rounded p-2 mb-2">{substitutePathParams(ep.url)}</div>
                    {hasQuery && (
                      <div className="mb-2 space-y-1">
                        <div className="text-xs text-gray-600">Query Parameters</div>
                        {parseQueryParams(ep.url).map((key) => (
                          <div key={key} className="flex items-center gap-2">
                            <div className="text-xs w-32 text-gray-700">{key}</div>
                            <Input
                              value={(customParams[ep.url]?.[key] ?? '')}
                              onChange={(e)=> setCustomParams(prev=> ({ ...prev, [ep.url]: { ...(prev[ep.url]||{}), [key]: e.target.value } }))}
                              placeholder={key === 'phoneNumber' ? testValue : ''}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                    {isWrite && ep.hasBody && (
                      <div className="mb-2">
                        <div className="text-xs text-gray-600 mb-1">Request JSON Body</div>
                        <textarea
                          className="w-full text-xs font-mono border rounded p-2 bg-white"
                          rows={6}
                          defaultValue={defaultBody}
                          onChange={(e)=> setCustomBodies(prev=> ({ ...prev, [ep.url]: e.target.value }))}
                        />
                      </div>
                    )}
                    <div className="flex items-center justify-end gap-2">
                      <Button onClick={()=>testEndpoint(ep)} disabled={!!loading[ep.id]}>{loading[ep.id]? 'Testing…' : 'Test'}</Button>
                    </div>
                    {r && (
                      <div className="mt-3 border-t pt-2 text-sm">
                        <div className="flex items-center justify-between">
                          <div className={`flex items-center gap-2 ${r.ok?'text-green-700':'text-red-700'}`}>
                            <span className="font-semibold">{r.ok ? 'Success' : 'Error'}</span>
                          </div>
                          <div className="text-xs text-gray-600">{new Date(r.when).toLocaleString()} • {r.totalMs} ms</div>
                        </div>
                        <div className="mt-2 space-y-2">
                          {r.steps.map((s, i)=> (
                            <div key={i} className="p-2 rounded border bg-gray-50">
                              <div className="flex items-center justify-between">
                                <div className="font-medium">{i+1}. {s.title}</div>
                                <div className={`text-xs ${s.ok?'text-green-700':'text-red-700'}`}>{s.ok? '✅' : '❌'} {s.status} • {s.ms} ms</div>
                              </div>
                              <pre className="mt-1 text-xs whitespace-pre-wrap break-words">{typeof s.body==='string'? s.body : JSON.stringify(s.body, null, 2)}</pre>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// Helpers
function deepReplace(value: any, map: Record<string,string>): any {
  if (typeof value === 'string') {
    let out = value
    Object.entries(map).forEach(([k,v]) => {
      out = out.split(`{${k}}`).join(v)
    })
    return out
  }
  if (Array.isArray(value)) return value.map(v => deepReplace(v, map))
  if (value && typeof value === 'object') {
    const obj: any = {}
    Object.entries(value).forEach(([k,v]) => { obj[k] = deepReplace(v, map as any) })
    return obj
  }
  return value
}

function buildProviderEndpoints(): Endpoint[] {
  const json = { 'Content-Type': 'application/json' }
  const body = { phoneNumber: '{phoneNumber}' }
  const rcAuth: Endpoint = { id:'POST-/api/v1/ringcentral/auth', name:'RingCentral Auth', url:'/api/v1/ringcentral/auth', method:'POST', tags:['RingCentral'], headers: json }
  const rcPrereq = [rcAuth]
  const tenantAdmin = Object.assign({}, json, { 'X-Org-Id': '1', 'X-User-Id': '1', 'X-Role': 'superadmin' })
  // Only include FreeDNC/Postgres-backed tester items
  return [
    // Statuses (CRMStatus summary)
    { id:'GET-/api/v1/statuses', name:'CRM Statuses', url:'/api/v1/statuses', method:'GET', tags:['Core'] },
    // FreeDNC-style utilities
    { id:'POST-/api/check_number', name:'Check Single Number', url:'/api/check_number', method:'POST', tags:['Core'], headers: json, requestBodyExample: { phone_number: '{phoneNumber}' } },
    { id:'POST-/api/check_tps_database', name:'Check TPS DB DNC', url:'/api/check_tps_database', method:'POST', tags:['Core'], headers: json, requestBodyExample: { limit: 100 } },
    { id:'POST-/api/cases_by_phone', name:'Cases By Phone (TPS)', url:'/api/cases_by_phone', method:'POST', tags:['Core'], headers: json, requestBodyExample: { phone_number: '{phoneNumber}' } },
    { id:'POST-/api/run_automation', name:'Run DNC Automation (stub)', url:'/api/run_automation', method:'POST', tags:['Core'], headers: json, requestBodyExample: { phone_number: '{phoneNumber}' } },
    { id:'POST-/api/cookies/refresh', name:'Refresh FreeDNC Cookies', url:'/api/cookies/refresh', method:'POST', tags:['Core'] },
    // (provider endpoints removed from tester)
    // Tenants (admin headers)
    { id:'GET-/api/v1/tenants/propagation/attempts', name:'Tenant DNC History (by Org)', url:'/api/v1/tenants/propagation/attempts/1', method:'GET', tags:['Tenants'], headers: tenantAdmin },
    { id:'GET-/api/v1/tenants/system/services', name:'System Services (admin)', url:'/api/v1/tenants/system/services', method:'GET', tags:['Tenants'], headers: tenantAdmin },
    { id:'POST-/api/v1/tenants/system/test', name:'System Provider Test (admin)', url:'/api/v1/tenants/system/test/{phoneNumber}', method:'POST', tags:['Tenants'], headers: tenantAdmin },
  ]
}

function resolveBodyPlaceholders(body: any) {
  if (body === undefined) return undefined
  const val = (document.querySelector('input[placeholder="5618189087"]') as HTMLInputElement)?.value || ''
  const map = { phoneNumber: val, phone_number: val }
  return deepReplace(body, map)
}


