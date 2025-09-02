import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { Phone, Upload, X, AlertCircle, CheckCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { cn, formatPhoneNumber, validatePhoneNumber, normalizePhoneNumber } from '@/lib/utils'

const phoneInputSchema = z.object({
  phone_numbers: z.string().min(1, 'Please enter at least one phone number'),
  notes: z.string().optional(),
})

type PhoneInputFormData = z.infer<typeof phoneInputSchema>

interface PhoneInputProps {
  onNumbersSubmit: (numbers: string[], notes?: string) => void
  isLoading?: boolean
}

export const PhoneInput: React.FC<PhoneInputProps> = ({
  onNumbersSubmit,
  isLoading = false,
}) => {
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [validNumbers, setValidNumbers] = useState<string[]>([])
  const [invalidNumbers, setInvalidNumbers] = useState<string[]>([])

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
  } = useForm<PhoneInputFormData>({
    resolver: zodResolver(phoneInputSchema),
  })

  const phoneNumbers = watch('phone_numbers', '')

  const validateAndFormatNumbers = (input: string) => {
    const numbers = input
      .split(/[\n,;]/)
      .map(num => num.trim())
      .filter(num => num.length > 0)

    const valid: string[] = []
    const invalid: string[] = []
    const errors: string[] = []

    numbers.forEach((number, index) => {
      const normalized = normalizePhoneNumber(number)
      
      if (!validatePhoneNumber(normalized)) {
        invalid.push(number)
        errors.push(`Line ${index + 1}: Invalid phone number format`)
      } else {
        valid.push(normalized)
      }
    })

    setValidNumbers(valid)
    setInvalidNumbers(invalid)
    setValidationErrors(errors)

    return { valid, invalid, errors }
  }

  const handlePhoneNumbersChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const input = e.target.value
    if (input) {
      validateAndFormatNumbers(input)
    } else {
      setValidNumbers([])
      setInvalidNumbers([])
      setValidationErrors([])
    }
  }

  const onSubmit = (data: PhoneInputFormData) => {
    const { valid } = validateAndFormatNumbers(data.phone_numbers)
    
    if (valid.length > 0) {
      onNumbersSubmit(valid, data.notes)
      reset()
      setValidNumbers([])
      setInvalidNumbers([])
      setValidationErrors([])
    }
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      // Update the form value
      const textarea = document.querySelector('textarea[name="phone_numbers"]') as HTMLTextAreaElement
      if (textarea) {
        textarea.value = content
        validateAndFormatNumbers(content)
      }
    }
    reader.readAsText(file)
  }

  const clearInput = () => {
    reset()
    setValidNumbers([])
    setInvalidNumbers([])
    setValidationErrors([])
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="bg-white shadow-lg rounded-lg border-0 overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-red-600 to-red-800 py-4 px-6">
          <CardTitle className="text-xl font-semibold text-white flex items-center gap-2">
            <Phone className="w-5 h-5" />
            Do Not Call List Removal
          </CardTitle>
        </CardHeader>
        
        <CardContent className="p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="phone_numbers" className="text-sm font-medium">
                Phone Numbers
              </Label>
              <div className="relative">
                <Textarea
                  {...register('phone_numbers')}
                  id="phone_numbers"
                  placeholder="Enter phone numbers (one per line, comma-separated, or semicolon-separated)&#10;Example:&#10;(555) 123-4567&#10;555-987-6543&#10;5551234567"
                  className={cn(
                    "min-h-[200px] resize-none",
                    errors.phone_numbers && "border-destructive focus-visible:ring-destructive"
                  )}
                  onChange={handlePhoneNumbersChange}
                />
                <div className="absolute top-2 right-2 flex gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => document.getElementById('file-upload')?.click()}
                    className="h-8 w-8 p-0"
                  >
                    <Upload className="w-4 h-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={clearInput}
                    className="h-8 w-8 p-0"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                <input
                  id="file-upload"
                  type="file"
                  accept=".txt,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </div>
              {errors.phone_numbers && (
                <p className="text-sm text-destructive">{errors.phone_numbers.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes" className="text-sm font-medium">
                Notes (Optional)
              </Label>
              <Input
                {...register('notes')}
                id="notes"
                placeholder="Add any notes about this removal request..."
              />
            </div>

            {/* Validation Summary */}
            {(validNumbers.length > 0 || invalidNumbers.length > 0) && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium">Validation Summary</h4>
                
                {validNumbers.length > 0 && (
                  <div className="flex items-center gap-2 text-sm text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    <span>{validNumbers.length} valid phone number(s)</span>
                  </div>
                )}
                
                {invalidNumbers.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm text-red-600">
                      <AlertCircle className="w-4 h-4" />
                      <span>{invalidNumbers.length} invalid phone number(s)</span>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-md p-3">
                      <ul className="text-xs text-red-700 space-y-1">
                        {validationErrors.slice(0, 5).map((error, index) => (
                          <li key={index}>{error}</li>
                        ))}
                        {validationErrors.length > 5 && (
                          <li>... and {validationErrors.length - 5} more errors</li>
                        )}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <Button
                type="submit"
                disabled={isLoading || validNumbers.length === 0}
                className="flex-1 bg-red-600 hover:bg-red-700"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Processing...
                  </>
                ) : (
                  `Submit ${validNumbers.length > 0 ? `(${validNumbers.length} numbers)` : ''} for Removal`
                )}
              </Button>
              
              <Button
                type="button"
                variant="outline"
                onClick={clearInput}
                disabled={isLoading}
              >
                Clear
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  )
}



