import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { motion } from 'framer-motion'
import { Phone, Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Textarea } from '../ui/textarea'
import { Label } from '../ui/label'
import { cn, validatePhoneNumber, normalizePhoneNumber } from '@/lib/utils'
import { API_BASE_URL } from '@/lib/api'
import { useAppSelector } from '@/lib/hooks'

interface PhoneInputFormData {
  phone_numbers: string
  notes?: string
}

interface PhoneInputProps {
  onNumbersSubmit: (numbers: string[], notes?: string) => Promise<void>
  isLoading: boolean
}

export const PhoneInput: React.FC<PhoneInputProps> = ({ onNumbersSubmit, isLoading }) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [selectedChannels, setSelectedChannels] = useState<string[]>(['voice'])
  
  // Reactively read role and IDs from Redux to update immediately when dropdown changes
  const { role, organizationId, userId } = useAppSelector((s) => s.demoAuth)

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<PhoneInputFormData>()

  const onSubmit = async (data: PhoneInputFormData) => {
    setIsSubmitting(true)
    setError(null)
    setSuccess(null)

    try {
      // Parse phone numbers from textarea
      const phoneNumbers = data.phone_numbers
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(normalizePhoneNumber)

      if (phoneNumbers.length === 0) {
        setError('Please enter at least one phone number')
        return
      }

      // Validate all phone numbers
      const invalidNumbers = phoneNumbers.filter(num => !validatePhoneNumber(num))
      if (invalidNumbers.length > 0) {
        setError(`Invalid phone numbers: ${invalidNumbers.join(', ')}`)
        return
      }

      // Submit phone numbers (only for admin/owner)
      await onNumbersSubmit(phoneNumbers, data.notes)
      
      setSuccess(`Successfully submitted ${phoneNumbers.length} phone numbers`)
      reset()
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  // handleDncPrecheck kept for reference; currently unused in admin flow

  const handleReset = () => {
    reset()
    setError(null)
    setSuccess(null)
  }

  // User-facing DNC Request form (inline minimal)
  const submitDncRequest = async () => {
    try {
      const orgId = organizationId || 1
      const reqUserId = userId || 1
      const phoneRaw = (document.getElementById('phone_numbers') as HTMLTextAreaElement)?.value.split('\n').find(l => l.trim()) || ''
      const phone = normalizePhoneNumber(phoneRaw.trim())
      if (!phone) {
        setError('Enter at least one phone number to request DNC')
        return
      }
      // Basic UX polish: choose channels/reason
      const reason = (document.getElementById('dnc_reason') as HTMLInputElement)?.value || 'user request'
      const headers = { 'X-Org-Id': String(orgId), 'X-User-Id': String(reqUserId), 'X-Role': String(role || 'member') }
      if (!selectedChannels.length) {
        setError('Select at least one channel (Call, SMS, Email)')
        return
      }
      for (const channel of selectedChannels) {
        const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-requests/${orgId}`,
          { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify({ phone_e164: phone, reason, channel, requested_by_user_id: reqUserId }) })
        if (!resp.ok) throw new Error('Failed to submit DNC request')
      }
      setSuccess('DNC request submitted for review')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit DNC request')
    }
  }

  const isAdmin = role === 'admin' || role === 'owner'
  const isMember = role === 'member'

  return (
    <Card className="border-2 border-dashed border-blue-300 hover:border-blue-400 transition-colors">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-blue-600">
          <Phone className="h-5 w-5" />
          Add Phone Numbers
        </CardTitle>
        <CardDescription>
          Enter phone numbers to be removed from Do Not Call lists across all CRM systems
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="phone_numbers" className="text-sm font-medium text-gray-700">
              Phone Numbers (one per line)
            </Label>
            <Textarea
              id="phone_numbers"
              placeholder="Enter phone numbers here...&#10;Example:&#10;555-123-4567&#10;(555) 987-6543&#10;555.123.4567"
              className={cn(
                "mt-1 min-h-[120px] resize-none",
                errors.phone_numbers && "border-red-300 focus:border-red-500 focus:ring-red-500"
              )}
              {...register('phone_numbers', {
                required: 'Phone numbers are required',
                validate: (value) => {
                  if (!value.trim()) return 'Phone numbers are required'
                  const lines = value.split('\n').filter(line => line.trim().length > 0)
                  if (lines.length === 0) return 'Please enter at least one phone number'
                  return true
                }
              })}
            />
            {errors.phone_numbers && (
              <p className="mt-1 text-sm text-red-600">{errors.phone_numbers.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="notes" className="text-sm font-medium text-gray-700">
              Notes (optional)
            </Label>
            <Textarea
              id="notes"
              placeholder="Add any notes about these phone numbers..."
              className="mt-1 resize-none"
              {...register('notes')}
            />
          </div>

          {/* Error Display */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 bg-red-50 border border-red-200 rounded-lg"
            >
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">{error}</span>
              </div>
            </motion.div>
          )}

          {/* Success Display */}
          {success && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 bg-green-50 border border-green-200 rounded-lg"
            >
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle className="h-4 w-4" />
                <span className="text-sm">{success}</span>
              </div>
            </motion.div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {isAdmin && (
              <Button
                type="submit"
                disabled={isSubmitting || isLoading}
                className="bg-blue-600 hover:bg-blue-700 text-white whitespace-nowrap"
              >
                {isSubmitting || isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    {isSubmitting ? 'Submitting...' : 'Loading...'}
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Run Number Check
                  </>
                )}
              </Button>
            )}
            {/* Cross-check button removed in admin flow */}
            {isMember && (
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-gray-700">Channels</span>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { key: 'voice', label: 'Call' },
                      { key: 'sms', label: 'SMS' },
                      { key: 'email', label: 'Email' },
                    ].map((c) => (
                      <button
                        key={c.key}
                        type="button"
                        onClick={() => setSelectedChannels((prev) => prev.includes(c.key) ? prev.filter(v => v !== c.key) : [...prev, c.key])}
                        className={cn(
                          'px-3 py-1 rounded border text-sm',
                          selectedChannels.includes(c.key)
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                        )}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label htmlFor="dnc_reason" className="text-xs">Reason</Label>
                  <input id="dnc_reason" className="border rounded px-2 py-1 text-sm" placeholder="Customer opt-out" />
                </div>
              </div>
            )}
            {isMember && (
              <Button
                type="button"
                variant="outline"
                onClick={submitDncRequest}
                disabled={isSubmitting || isLoading}
                className="flex-shrink-0 whitespace-nowrap"
              >
                Request DNC
              </Button>
            )}
            
            <Button
              type="button"
              variant="outline"
              onClick={handleReset}
              disabled={isSubmitting || isLoading}
              className="flex-shrink-0 whitespace-nowrap"
            >
              Reset
            </Button>
          </div>
        </form>
        
      </CardContent>
    </Card>
  )
}




