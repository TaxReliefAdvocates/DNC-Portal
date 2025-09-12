import React, { useEffect, useState } from 'react'
import { useAppSelector } from '@/lib/hooks'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'

type ServiceRow = { key: string; enabled: boolean }

const getHeaders = (role: string, orgId: number, userId: number) => ({
  'Content-Type': 'application/json',
  'X-Role': role,
  'X-Org-Id': String(orgId || 1),
  'X-User-Id': String(userId || 1),
})

export const SystemSettings: React.FC = () => {
  const { role, organizationId, userId } = useAppSelector((s) => s.demoAuth)
  const isSuperAdmin = role === 'superadmin'

  const [open] = useState(true)
  const [services, setServices] = useState<ServiceRow[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserName, setNewUserName] = useState('')
  const [superAdminIds, setSuperAdminIds] = useState<Record<number, boolean>>({})
  const [loading, setLoading] = useState(false)
  const [testPhone, setTestPhone] = useState('5551234567')
  const [testLog, setTestLog] = useState<string>('')
  const [rcLog, setRcLog] = useState<string>('')
  const [rcStatus, setRcStatus] = useState<any | null>(null)
  const [rcBusy, setRcBusy] = useState(false)

  // Always open in page mode

  useEffect(() => {
    if (!open || !isSuperAdmin) return
    ;(async () => {
      try {
        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/system/services`, { headers: getHeaders(role, organizationId, userId) })
        if (resp.ok) setServices(await resp.json())
        // fetch users (minimal: reuse tenants GET /users)
        const u = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/users`)
        if (u.ok) setUsers(await u.json())
      } catch {}
    })()
  }, [open, isSuperAdmin])

  const toggle = async (key: string, enabled: boolean) => {
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/system/services/${key}`, {
        method: 'PUT',
        headers: getHeaders(role, organizationId, userId),
        body: JSON.stringify({ enabled }),
      })
      if (resp.ok) {
        setServices((rows) => rows.map((r) => (r.key === key ? { ...r, enabled } : r)))
      }
    } catch {}
  }

  const testProvider = async (key: string) => {
    setLoading(true)
    setTestLog('')
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/system/test/${key}`, {
        method: 'POST',
        headers: getHeaders(role, organizationId, userId),
        body: JSON.stringify({ phone_e164: testPhone }),
      })
      const data = await resp.json()
      setTestLog(`${key}: ${data.success ? 'OK' : 'FAILED'} (${data.status_code})\n${data.response || ''}`)
    } catch (e) {
      setTestLog(`${key}: ERROR ${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const rcAuthStatus = async () => {
    setRcBusy(true)
    setRcLog('')
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ringcentral/auth/status`)
      const data = await resp.json()
      setRcStatus(data)
      setRcLog(JSON.stringify(data, null, 2))
    } catch (e) {
      setRcLog(`Error: ${(e as Error).message}`)
    } finally { setRcBusy(false) }
  }

  const rcListBlocked = async () => {
    setRcBusy(true)
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ringcentral/dnc/list`)
      const data = await resp.json()
      setRcLog(JSON.stringify(data, null, 2))
    } catch (e) { setRcLog(`Error: ${(e as Error).message}`) } finally { setRcBusy(false) }
  }

  const rcSearch = async () => {
    setRcBusy(true)
    try {
      const pn = encodeURIComponent(testPhone)
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ringcentral/dnc/search/${pn}`)
      const data = await resp.json()
      setRcLog(JSON.stringify(data, null, 2))
    } catch (e) { setRcLog(`Error: ${(e as Error).message}`) } finally { setRcBusy(false) }
  }

  const rcAdd = async () => {
    setRcBusy(true)
    try {
      const url = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/crm/ringcentral/dnc/add?phone_number=${encodeURIComponent(testPhone)}&label=${encodeURIComponent('API Block')}`
      const resp = await fetch(url, { method: 'POST' })
      const data = await resp.json()
      setRcLog(JSON.stringify(data, null, 2))
    } catch (e) { setRcLog(`Error: ${(e as Error).message}`) } finally { setRcBusy(false) }
  }

  if (!isSuperAdmin) return null

  return open ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Card>
            <CardHeader><CardTitle>Providers</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {services.map((s) => (
                  <div key={s.key} className="flex items-center justify-between border rounded p-2">
                    <span className="capitalize">{s.key}</span>
                    <label className="flex items-center gap-2 text-sm">
                      <span>{s.enabled ? 'Enabled' : 'Disabled'}</span>
                      <input type="checkbox" checked={s.enabled} onChange={(e)=>toggle(s.key, e.target.checked)} />
                    </label>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Test Endpoints</CardTitle></CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 mb-2">
                <Input value={testPhone} onChange={(e)=>setTestPhone(e.target.value)} placeholder="E.164 or digits" />
              </div>
              <div className="flex flex-wrap gap-2 mb-2">
                {['ringcentral','convoso','ytel','logics'].map((k)=> (
                  <Button key={k} size="sm" variant="outline" onClick={()=>testProvider(k)} disabled={loading}>{k}</Button>
                ))}
              </div>
              <pre className="text-xs bg-gray-50 border rounded p-2 max-h-48 overflow-auto whitespace-pre-wrap">{testLog || 'Run a test to see response here.'}</pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>RingCentral Auth & DNC</CardTitle></CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 mb-2">
                <Input value={testPhone} onChange={(e)=>setTestPhone(e.target.value)} placeholder="Phone to add/search" />
              </div>
              <div className="flex flex-wrap gap-2 mb-2">
                <Button size="sm" variant="outline" onClick={rcAuthStatus} disabled={rcBusy}>Check Auth</Button>
                <Button size="sm" variant="outline" onClick={rcListBlocked} disabled={rcBusy}>List Blocked</Button>
                <Button size="sm" variant="outline" onClick={rcSearch} disabled={rcBusy}>Search Blocked</Button>
                <Button size="sm" variant="default" onClick={rcAdd} disabled={rcBusy}>Add to DNC</Button>
              </div>
              <pre className="text-xs bg-gray-50 border rounded p-2 max-h-48 overflow-auto whitespace-pre-wrap">{rcLog || 'Use the buttons above to interact with RingCentral.'}</pre>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader><CardTitle>Users & Roles (minimal)</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input placeholder="Email" value={newUserEmail} onChange={(e)=>setNewUserEmail(e.target.value)} />
                  <Input placeholder="Name" value={newUserName} onChange={(e)=>setNewUserName(e.target.value)} />
                  <Button
                    onClick={async ()=>{
                      try {
                        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/users`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: newUserEmail, name: newUserName }) })
                        if (resp.ok) {
                          const u = await resp.json()
                          setUsers([u, ...users])
                          setNewUserEmail(''); setNewUserName('')
                        }
                      } catch {}
                    }}
                  >Add</Button>
                </div>
                <div className="border rounded divide-y">
                  {users.map((u:any)=> (
                    <div key={u.id} className="p-2 flex items-center justify-between">
                      <div className="text-sm">
                        <div className="font-medium">{u.email}</div>
                        <div className="text-gray-600">{u.name || '—'}</div>
                      </div>
                      <label className="flex items-center gap-2 text-sm">
                        <span>System Admin</span>
                        <input type="checkbox" checked={!!superAdminIds[u.id]} onChange={(e)=> setSuperAdminIds({ ...superAdminIds, [u.id]: e.target.checked })} />
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
  ) : null
}


