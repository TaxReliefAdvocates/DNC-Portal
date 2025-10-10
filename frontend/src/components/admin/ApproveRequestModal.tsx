import React, { useState } from 'react'
import { Button } from '../ui/button'
import { Textarea } from '../ui/textarea'

export const ApproveRequestModal: React.FC<{
  phone: string
  requestedBy?: string
  reason?: string
  submitted?: string
  onApprove: (notes: string)=>Promise<void> | void
  onCancel: ()=>void
}>
= ({ phone, requestedBy, reason, submitted, onApprove, onCancel }) => {
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)

  const go = async () => {
    setLoading(true)
    await onApprove(notes)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-lg p-4">
        <div className="font-semibold mb-2">Approve DNC Request?</div>
        <div className="text-sm text-gray-700 mb-2">
          <div>Phone: <span className="font-medium">{phone}</span></div>
          {requestedBy && <div>Requested by: {requestedBy}</div>}
          {reason && <div>Reason: {reason}</div>}
          {submitted && <div>Submitted: {submitted}</div>}
        </div>
        <div className="text-sm text-gray-700 mb-3">
          This will add the number to DNC lists across RingCentral, Convoso, Ytel, Logics, and Genesys.
        </div>
        <div className="mb-3">
          <div className="text-xs text-gray-700 mb-1">Decision Notes (optional)</div>
          <Textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={go} disabled={loading}>{loading ? 'Approving…' : 'Approve & Propagate'}</Button>
        </div>
      </div>
    </div>
  )
}


