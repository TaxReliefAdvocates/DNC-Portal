import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'

type Row = { id:number; phone_e164:string; in_national_dnc:boolean; in_org_dnc:boolean; sample_date:string }

interface Props { organizationId:number; adminUserId:number }

export const AdminSamplesGaps: React.FC<Props> = ({ organizationId, adminUserId }) => {
  const [rows, setRows] = useState<Row[]>([])
  const [selected, setSelected] = useState<Record<number, boolean>>({})
  const [loading, setLoading] = useState(false)

  const acquireAuthHeaders = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = { 'Content-Type':'application/json','X-Org-Id':String(organizationId),'X-User-Id':String(adminUserId),'X-Role':'superadmin' }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) h['Authorization'] = `Bearer ${token}`
      }
    } catch {}
    return h
  }

  const load = async () => {
    setLoading(true)
    const headers = await acquireAuthHeaders()
    const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-samples/${organizationId}?only_gaps=true&limit=200`, { headers })
    const json = await resp.json()
    setRows(json)
    setLoading(false)
  }
  useEffect(()=>{ load() }, [])

  const ids = useMemo(()=> Object.entries(selected).filter(([,v])=>v).map(([k])=>Number(k)), [selected])

  const bulkAdd = async () => {
    if (ids.length===0) return
    const headers = await acquireAuthHeaders()
    await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-samples/${organizationId}/bulk_add_to_dnc`, {
      method:'POST', headers, body: JSON.stringify({ ids })
    })
    setSelected({})
    load()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>National DNC Gaps (not in org DNC)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 mb-3">
          <Button variant="outline" onClick={bulkAdd} disabled={ids.length===0}>Add selected to DNC</Button>
          <span className="text-sm text-gray-600">Selected: {ids.length}</span>
        </div>
        {loading ? (
          <div className="space-y-2">{Array.from({length:6}).map((_,i)=>(<div key={i} className="animate-pulse h-10 bg-gray-100 rounded" />))}</div>
        ) : rows.length===0 ? (
          <div className="text-sm text-gray-600">No gaps found.</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                <div className="flex items-center gap-2">
                  <input type="checkbox" checked={!!selected[r.id]} onChange={(e)=>setSelected({...selected, [r.id]: e.target.checked})} />
                  <div className="text-sm">
                    <div className="font-medium">{r.phone_e164}</div>
                    <div className="text-gray-600">Sample: {new Date(r.sample_date).toLocaleString()}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


