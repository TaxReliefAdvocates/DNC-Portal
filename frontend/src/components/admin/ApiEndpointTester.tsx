import React, { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Textarea } from '../ui/textarea'
import { API_BASE_URL } from '@/lib/api'

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

type Endpoint = {
  id: string
  name: string
  url: string
  method: Method
  tenantType: string
  description?: string
  headers?: Record<string, string>
  body?: string
  prereqs?: Endpoint[]
  authRequired?: boolean
}

type StepResult = { title: string; ok: boolean; status: number; ms: number; body: any }
type TestResult = { id: string; ok: boolean; totalMs: number; steps: StepResult[]; when: string }

const defaultSeed: Endpoint[] = [
  {
    id: 'rc-auth', name: 'RingCentral Auth Status', method: 'GET', tenantType: 'RingCentral',
    url: `${API_BASE_URL}/api/v1/ringcentral/auth/status`, description: 'Check backend JWT auth and discovered account/extension.'
  },
  {
    id: 'rc-search', name: 'RC: Search Blocked', method: 'GET', tenantType: 'RingCentral',
    url: `${API_BASE_URL}/api/v1/ringcentral/dnc/search/{id}`, description: 'Search blocked list for E.164 phone.',
    prereqs: [{ id: 'rc-auth', name: '', url: '', method: 'GET', tenantType: 'RingCentral' }], authRequired: true
  },
  {
    id: 'convoso-search', name: 'Convoso: DNC Search', method: 'GET', tenantType: 'Convoso',
    url: `${API_BASE_URL}/api/v1/convoso/dnc/search/{id}?phone_code=1&offset=0&limit=10`, description: 'Convoso DNC search'
  },
  {
    id: 'ytel-check', name: 'Ytel: DNC Check', method: 'GET', tenantType: 'Ytel',
    url: `${API_BASE_URL}/api/v1/ytel/dnc/check/{id}`, description: 'Ytel DNC check'
  },
  {
    id: 'systems', name: 'Systems Check', method: 'GET', tenantType: 'Consolidated',
    url: `${API_BASE_URL}/api/v1/systems-check?phone_number={id}`, description: 'Consolidated provider check'
  },
]

const groupBy = (arr: Endpoint[], key: (e: Endpoint)=>string) => {
  const m: Record<string, Endpoint[]> = {}
  arr.forEach(e => { const k = key(e); if (!m[k]) m[k]=[]; m[k].push(e) })
  return m
}

export const ApiEndpointTester: React.FC = () => {
  const [testValue, setTestValue] = useState('5618189087')
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [results, setResults] = useState<Record<string, TestResult>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Endpoint | null>(null)

  // Load/persist endpoints
  useEffect(()=>{
    const raw = localStorage.getItem('apiTester.endpoints')
    if (raw) {
      try { setEndpoints(JSON.parse(raw)) } catch { setEndpoints(defaultSeed) }
    } else setEndpoints(defaultSeed)
  }, [])
  useEffect(()=>{ localStorage.setItem('apiTester.endpoints', JSON.stringify(endpoints)) }, [endpoints])

  const groups = useMemo(()=> groupBy(endpoints, e=> e.tenantType || 'General'), [endpoints])

  const openNew = () => { setEditing({ id: crypto.randomUUID(), name: '', url: '', method: 'GET', tenantType: 'General', description: '', headers: { 'Content-Type':'application/json' }, body: '' }); setShowModal(true) }
  const openEdit = (ep: Endpoint) => { setEditing({ ...ep }); setShowModal(true) }
  const del = (id: string) => setEndpoints(prev => prev.filter(e=> e.id!==id))

  const save = () => {
    if (!editing) return
    if (!editing.name || !editing.url || !editing.method) return
    setEndpoints(prev => {
      const i = prev.findIndex(e=> e.id===editing.id)
      if (i>=0) { const next=[...prev]; next[i]=editing; return next }
      return [editing, ...prev]
    })
    setShowModal(false)
  }

  const substitute = (tpl: string) => tpl.replaceAll('{id}', encodeURIComponent(testValue || ''))

  const runStep = async (title: string, method: Method, url: string, headers?: Record<string,string>, body?: string): Promise<StepResult> => {
    const started = performance.now()
    try {
      const resp = await fetch(url, { method, headers, body: body && body.trim() ? substitute(body) : undefined })
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
        const url = substitute(pre.url || '') || substitute(ep.url)
        const s = await runStep(pre.name || 'OAuth / Prereq', pre.method || 'GET', url, pre.headers, pre.body)
        steps.push(s)
        if (!s.ok) break
      }
    }
    if (steps.every(s=> s.ok)) {
      const url = substitute(ep.url)
      const s = await runStep('API Call', ep.method, url, ep.headers, ep.body)
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
              <label className="text-sm text-gray-700">Test Value (replaces {'{id}'} in URLs)</label>
              <Input value={testValue} onChange={(e)=>setTestValue(e.target.value)} placeholder="5618189087" />
            </div>
            <div className="flex gap-2">
              <Button className="bg-green-600 hover:bg-green-700" onClick={openNew}>+ Add Endpoint</Button>
            </div>
          </div>
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
                    <div className="text-xs font-mono break-all bg-gray-50 border rounded p-2 mb-2">{substitute(ep.url)}</div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex gap-2">
                        <Button variant="outline" onClick={()=>openEdit(ep)}>Edit</Button>
                        <Button variant="outline" onClick={()=>del(ep.id)}>Delete</Button>
                      </div>
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

      {showModal && editing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center">
          <div className="bg-white rounded shadow-lg w-full max-w-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-lg font-semibold">{editing.id? 'Edit' : 'Add'} Endpoint</div>
              <button className="text-sm text-gray-600" onClick={()=>setShowModal(false)}>Close</button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="col-span-2">
                <label>Name</label>
                <Input value={editing.name} onChange={(e)=>setEditing({ ...editing, name: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label>URL</label>
                <Input value={editing.url} onChange={(e)=>setEditing({ ...editing, url: e.target.value })} />
              </div>
              <div>
                <label>Method</label>
                <select className="w-full border rounded px-2 py-1" value={editing.method} onChange={(e)=>setEditing({ ...editing, method: e.target.value as Method })}>
                  {['GET','POST','PUT','DELETE','PATCH'].map(m=> (<option key={m} value={m}>{m}</option>))}
                </select>
              </div>
              <div>
                <label>Tenant Type</label>
                <Input value={editing.tenantType} onChange={(e)=>setEditing({ ...editing, tenantType: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label>Description</label>
                <Input value={editing.description||''} onChange={(e)=>setEditing({ ...editing, description: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label>Headers (JSON)</label>
                <Textarea value={JSON.stringify(editing.headers||{}, null, 2)} onChange={(e)=>{
                  try { setEditing({ ...editing, headers: JSON.parse(e.target.value||'{}') }) } catch {}
                }} />
              </div>
              <div className="col-span-2">
                <label>Body (optional; supports {'{id}'} replacement)</label>
                <Textarea value={editing.body||''} onChange={(e)=>setEditing({ ...editing, body: e.target.value })} />
              </div>
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="outline" onClick={()=>setShowModal(false)}>Cancel</Button>
              <Button onClick={save} disabled={!editing.name || !editing.url}>Save</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


