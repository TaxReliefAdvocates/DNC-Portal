import React, { useMemo, useState } from 'react'
import { API_BASE_URL, apiCall } from '../../lib/api'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'
import { toast } from 'sonner'

function formatDigits(value: string): string {
  return (value || '').replace(/\D+/g, '')
}

export const RequestDNCModal: React.FC<{ organizationId: number; onClose: ()=>void; phoneNumber?: string }>
  = ({ organizationId, onClose, phoneNumber }) => {
  const [phone, setPhone] = useState(() => (phoneNumber ? formatDigits(phoneNumber) : ''))
  const [reason, setReason] = useState('Customer opt-out')
  const [channel, setChannel] = useState<'voice'|'sms'>('voice')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const errors = useMemo(() => {
    const e: Record<string, string> = {}
    const digits = formatDigits(phone)
    if (digits.length < 10) e.phone = 'Enter a valid 10+ digit phone number'
    if (!reason) e.reason = 'Select a reason'
    if (!channel) e.channel = 'Select a channel'
    return e
  }, [phone, reason, channel])

  const submit = async () => {
    if (Object.keys(errors).length) {
      toast.error('Please fix validation errors')
      return
    }
    setSubmitting(true)
    try {
      await apiCall(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${organizationId}`, {
        method: 'POST',
        body: JSON.stringify({ phone_e164: formatDigits(phone), reason, channel, notes })
      })
      toast.success('Request submitted successfully')
      onClose()
    } catch (e: any) {
      toast.error(`Failed to submit: ${e?.message || 'Unknown error'}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="font-semibold">Request DNC</div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>
        <div className="space-y-3">
          <div>
            <Label>Phone Number</Label>
            <Input value={phone} onChange={e=>setPhone(e.target.value)} placeholder="(555) 123-4567" />
            {errors.phone && <div className="text-xs text-red-600 mt-1">{errors.phone}</div>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Reason</Label>
              <select className="w-full border rounded px-2 py-1" value={reason} onChange={e=>setReason(e.target.value)}>
                <option>Customer opt-out</option>
                <option>Legal request</option>
                <option>Internal block</option>
                <option>Litigation risk</option>
              </select>
            </div>
            <div>
              <Label>Channel</Label>
              <select className="w-full border rounded px-2 py-1" value={channel} onChange={e=>setChannel(e.target.value as any)}>
                <option value="voice">Call</option>
                <option value="sms">SMS</option>
              </select>
            </div>
          </div>
          <div>
            <Label>Notes (optional)</Label>
            <Textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={submitting}>{submitting ? 'Submitting…' : 'Submit'}</Button>
          </div>
        </div>
      </div>
    </div>
  )
}


