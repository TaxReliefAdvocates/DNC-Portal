import React, { useEffect, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Button } from '../ui/button'

type Row = {
  id: number
  phone_e164: string
  company: string
  case_number?: string
  received_at?: string | null
  status: string
  notes?: string
}

interface Props {
  organizationId: number
  adminUserId: number
}

export const AdminLitigation: React.FC<Props> = ({ organizationId, adminUserId }) => {
  const [rows, setRows] = useState<Row[]>([])
  const [q, setQ] = useState('')
  const [cursor, setCursor] = useState<number | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)

  const [phone, setPhone] = useState('')
  const [company, setCompany] = useState('')
  const [caseNumber, setCaseNumber] = useState('')
  const [notes, setNotes] = useState('')

  const headers = {
    'Content-Type': 'application/json',
    'X-Org-Id': String(organizationId),
    'X-User-Id': String(adminUserId),
    'X-Role': 'owner',
  }

  const load = async (append=false) => {
    setLoading(true)
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (cursor) params.set('cursor', String(cursor))
    params.set('limit','50')
    const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/litigations/${organizationId}?${params.toString()}`, { headers })
    const newRows: Row[] = await resp.json()
    setRows(append ? [...rows, ...newRows] : newRows)
    setHasMore(newRows.length===50)
    setCursor(newRows.length ? newRows[newRows.length-1].id : null)
    setLoading(false)
  }

  useEffect(()=>{ setCursor(null); load(false) }, [q])

  const add = async () => {
    if (!phone || !company) return
    await fetch(`${API_BASE_URL}/api/v1/tenants/litigations/${organizationId}`, {
      method:'POST', headers, body: JSON.stringify({ phone_e164: phone, company, case_number: caseNumber, notes })
    })
    setPhone(''); setCompany(''); setCaseNumber(''); setNotes('')
    setCursor(null)
    load(false)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>TCPA Litigation Records</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mb-3">
          <div className="md:col-span-2">
            <Label className="text-xs">Search</Label>
            <Input placeholder="Phone, company, case #" value={q} onChange={(e)=>setQ(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mb-4">
          <div>
            <Label className="text-xs">Phone (digits)</Label>
            <Input value={phone} onChange={(e)=>setPhone(e.target.value)} placeholder="e.g. 5618189087" />
          </div>
          <div className="md:col-span-2">
            <Label className="text-xs">Company</Label>
            <Input value={company} onChange={(e)=>setCompany(e.target.value)} placeholder="Company name" />
          </div>
          <div>
            <Label className="text-xs">Case #</Label>
            <Input value={caseNumber} onChange={(e)=>setCaseNumber(e.target.value)} placeholder="Optional" />
          </div>
          <div className="md:col-span-2 flex items-end">
            <Button onClick={add}>Add</Button>
          </div>
        </div>

        {loading && rows.length===0 ? (
          <div className="space-y-2">
            {Array.from({length:5}).map((_,i)=> (<div key={i} className="animate-pulse h-10 bg-gray-100 rounded" />))}
          </div>
        ) : rows.length===0 ? (
          <div className="text-sm text-gray-600">No litigation records</div>
        ) : (
          <div className="space-y-2">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                <div className="text-sm">
                  <div className="font-medium">{r.phone_e164} • {r.company}</div>
                  <div className="text-gray-600">Case: {r.case_number || '—'} • Status: {r.status}</div>
                </div>
              </div>
            ))}
            {hasMore && (
              <div className="text-center pt-2">
                <Button variant="outline" onClick={()=>load(true)}>Load more</Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


