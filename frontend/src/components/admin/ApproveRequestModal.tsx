import React, { useState } from 'react'
import { Button } from '../ui/button'
import { Textarea } from '../ui/textarea'

export const ApproveRequestModal: React.FC<{
  phone: string
  requestedBy?: string
  reason?: string
  submitted?: string
  systemsCheckResults?: any
  onApprove: (notes: string, propagateTo: string[])=>Promise<void> | void
  onCancel: ()=>void
}>
= ({ phone, requestedBy, reason, submitted, systemsCheckResults, onApprove, onCancel }) => {
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [selection, setSelection] = useState<Record<string, boolean>>({
    ringcentral: true,
    convoso: true,
    ytel: true,
    logics: true,
    genesys: true,
    dnc: true,
  })

  const toggle = (k: string, v: boolean) => setSelection(prev => ({ ...prev, [k]: v }))

  const providers = ['dnc','ringcentral','convoso','ytel','logics','genesys']
  const alreadyOn = (key: string) => Boolean(systemsCheckResults?.providers?.[key]?.listed)
  const effectiveSelection = providers.filter(k => selection[k])

  const go = async () => {
    setLoading(true)
    await onApprove(notes, effectiveSelection)
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
          Current Status Across Systems
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs mb-3">
          {providers.map((k) => (
            <div key={k} className="flex items-center justify-between border rounded p-2">
              <div className="capitalize">{k === 'dnc' ? 'National DNC' : k}</div>
              <div className="flex items-center gap-2">
                <span className={`px-1 py-0.5 rounded ${alreadyOn(k) ? 'bg-green-100 text-green-800' : (systemsCheckResults ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700')}`}>
                  {systemsCheckResults ? (alreadyOn(k) ? 'On DNC' : 'Not Listed') : 'Unknown'}
                </span>
                <input type="checkbox" checked={selection[k]} onChange={(e)=>toggle(k, e.target.checked)} disabled={alreadyOn(k)} />
              </div>
            </div>
          ))}
        </div>
        <div className="text-xs text-gray-600 mb-2">Will update {effectiveSelection.length} of {providers.length} systems</div>
        <div className="mb-3">
          <div className="text-xs text-gray-700 mb-1">Decision Notes (optional)</div>
          <Textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={go} disabled={loading || !systemsCheckResults}>{loading ? 'Approving…' : 'Approve & Propagate Selected'}</Button>
        </div>
      </div>
    </div>
  )
}


