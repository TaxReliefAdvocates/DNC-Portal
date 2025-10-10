import React, { useState } from 'react'
import { Button } from '../ui/button'
import { Textarea } from '../ui/textarea'

export const RejectRequestModal: React.FC<{
  phone: string
  onReject: (notes: string)=>Promise<void> | void
  onCancel: ()=>void
}>
= ({ phone, onReject, onCancel }) => {
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const go = async () => {
    if (!notes.trim()) { setError('Rejection notes are required'); return }
    setError(null)
    setLoading(true)
    await onReject(notes)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-lg p-4">
        <div className="font-semibold mb-2">Reject DNC Request?</div>
        <div className="text-sm text-gray-700 mb-2">Phone: <span className="font-medium">{phone}</span></div>
        <div className="mb-3">
          <div className="text-xs text-gray-700 mb-1">Please provide a reason for rejection</div>
          <Textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} />
          {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={go} disabled={loading}>{loading ? 'Rejecting…' : 'Reject Request'}</Button>
        </div>
      </div>
    </div>
  )
}


