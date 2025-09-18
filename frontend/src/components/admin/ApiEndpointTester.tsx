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
          const url = path
          const name = op?.summary || `${m} ${path}`
          const tags: string[] = Array.isArray(op?.tags) ? op.tags : ['Untagged']
          let example: any = undefined
          try {
            example = op?.requestBody?.content?.['application/json']?.example
              || op?.requestBody?.content?.['application/json']?.examples?.[0]
          } catch {}
          // Heuristic prereq for RingCentral auth
          const prereqs: Endpoint[] = url.includes('/ringcentral/') ? [{ id:'rc-auth', name:'OAuth Status', url: `${API_BASE_URL}/api/v1/ringcentral/auth/status`, method:'GET', tags:['RingCentral'] }] : []
          out.push({ id, name, url, method: m, tags, description: op?.description, requestBodyExample: example, headers: { 'Content-Type': 'application/json' }, prereqs })
        })
      })
      setEndpoints(out)
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
      const payload = body !== undefined ? (typeof body === 'string' ? body : JSON.stringify(body)) : undefined
      const resp = await fetch(buildUrl(urlOrPath), { method, headers, body: payload })
      const txt = await resp.text()
      let data: any = txt
      try { data = JSON.parse(txt) } catch {}
      return { title, ok: resp.ok, status: resp.status, ms: Math.round(performance.now()-started), body: data }
    } catch (e:any) {
      return { title, ok: false, status: 0, ms: Math.round(performance.now()-started), body: String(e?.message||e) }
    }
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
      const s = await runStep('API Call', ep.method, url, ep.headers, ep.requestBodyExample)
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


