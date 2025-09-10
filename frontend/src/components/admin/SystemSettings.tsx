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

  const [open, setOpen] = useState(false)
  const [services, setServices] = useState<ServiceRow[]>([])
  const [loading, setLoading] = useState(false)
  const [testPhone, setTestPhone] = useState('5551234567')
  const [testLog, setTestLog] = useState<string>('')

  useEffect(() => {
    const handler = () => setOpen(true)
    window.addEventListener('open-system-settings' as any, handler)
    return () => window.removeEventListener('open-system-settings' as any, handler)
  }, [])

  useEffect(() => {
    if (!open || !isSuperAdmin) return
    ;(async () => {
      try {
        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/tenants/system/services`, { headers: getHeaders(role, organizationId, userId) })
        if (resp.ok) setServices(await resp.json())
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

  if (!isSuperAdmin) return null

  return open ? (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center">
      <div className="bg-white rounded shadow-lg w-full max-w-3xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-lg font-semibold">System Settings</div>
          <button className="text-sm text-gray-600" onClick={() => setOpen(false)}>Close</button>
        </div>
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
        </div>
      </div>
    </div>
  ) : null
}


