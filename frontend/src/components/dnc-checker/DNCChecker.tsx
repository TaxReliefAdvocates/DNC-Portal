import React, { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload, FileText, CheckCircle, XCircle, Download, AlertCircle } from 'lucide-react'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'

interface DNCResult {
  original_data: string[]
  phone_number: string
  is_dnc: boolean
  dnc_source: string | null
  status: string
  notes: string | null
}

interface DNCResponse {
  success: boolean
  total_records: number
  dnc_matches: number
  safe_to_call: number
  data: DNCResult[]
  processed_at: string
  filename: string
}

export const DNCChecker: React.FC = () => {
  const [file, setFile] = useState<File | null>(null)
  const [columnIndex, setColumnIndex] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState<DNCResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (selectedFile: File) => {
    if (selectedFile.type !== 'text/csv' && !selectedFile.name.endsWith('.csv')) {
      setError('Please select a valid CSV file')
      return
    }
    
    if (selectedFile.size > 10 * 1024 * 1024) { // 10MB limit
      setError('File size must be less than 10MB')
      return
    }
    
    setFile(selectedFile)
    setError(null)
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0])
    }
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0])
    }
  }

  const processFile = async () => {
    if (!file) return

    setIsProcessing(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('column_index', columnIndex.toString())

      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/dnc/process-dnc`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to process file')
      }

      const result = await response.json()
      setResults(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsProcessing(false)
    }
  }

  const downloadResults = () => {
    if (!results) return

    const csvContent = [
      ['Phone Number', 'Is DNC', 'DNC Source', 'Status', 'Notes', 'Original Data'],
      ...results.data.map(row => [
        row.phone_number,
        row.is_dnc ? 'Yes' : 'No',
        row.dnc_source || 'N/A',
        row.status,
        row.notes || 'N/A',
        row.original_data.join(', ')
      ])
    ].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dnc_results_${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }

  const resetForm = () => {
    setFile(null)
    setColumnIndex(0)
    setResults(null)
    setError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h2 className="text-3xl font-bold text-gray-900 mb-2">
          DNC Checker
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Upload a CSV file to check phone numbers against Do Not Call lists. 
          Ensure compliance across all CRM systems.
        </p>
      </motion.div>

      {/* File Upload Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="border-2 border-dashed border-blue-300 hover:border-blue-400 transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-600">
              <Upload className="h-5 w-5" />
              Upload CSV File
            </CardTitle>
            <CardDescription>
              Drag and drop your CSV file here, or click to browse
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`relative p-8 text-center transition-colors ${
                dragActive ? 'bg-blue-50' : 'bg-gray-50'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileInput}
                className="hidden"
              />
              
              <div className="space-y-4">
                <Upload className="h-12 w-12 mx-auto text-blue-500" />
                
                {file ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 justify-center text-green-600">
                      <FileText className="h-5 w-5" />
                      <span className="font-medium">{file.name}</span>
                    </div>
                    <p className="text-sm text-gray-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-gray-600 mb-2">
                      <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-sm text-gray-500">
                      CSV files only, max 10MB
                    </p>
                  </div>
                )}
                
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-white hover:bg-gray-50"
                >
                  Choose File
                </Button>
              </div>
            </div>

            {/* Column Index Input */}
            {file && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-6 p-4 bg-blue-50 rounded-lg"
              >
                <Label htmlFor="columnIndex" className="text-sm font-medium text-gray-700">
                  Phone Number Column Index (0-based)
                </Label>
                <div className="flex items-center gap-2 mt-2">
                  <Input
                    id="columnIndex"
                    type="number"
                    min="0"
                    value={columnIndex}
                    onChange={(e) => setColumnIndex(parseInt(e.target.value) || 0)}
                    className="w-20"
                  />
                  <span className="text-sm text-gray-500">
                    Column {columnIndex} will be processed for phone numbers
                  </span>
                </div>
              </motion.div>
            )}

            {/* Error Display */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg"
              >
                <div className="flex items-center gap-2 text-red-700">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">{error}</span>
                </div>
              </motion.div>
            )}

            {/* Action Buttons */}
            {file && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 flex gap-3 justify-center"
              >
                <Button
                  onClick={processFile}
                  disabled={isProcessing}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {isProcessing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="h-4 w-4 mr-2" />
                      Process File
                    </>
                  )}
                </Button>
                
                <Button
                  variant="outline"
                  onClick={resetForm}
                  disabled={isProcessing}
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Reset
                </Button>
              </motion.div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Results Section */}
      {results && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-green-600">Processing Complete</CardTitle>
                  <CardDescription>
                    {results.filename} - {results.total_records} records processed
                  </CardDescription>
                </div>
                <Button
                  onClick={downloadResults}
                  variant="outline"
                  className="bg-green-50 hover:bg-green-100 border-green-200"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download Results
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Summary Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{results.total_records}</div>
                  <div className="text-sm text-gray-600">Total Records</div>
                </div>
                <div className="text-center p-4 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">{results.dnc_matches}</div>
                  <div className="text-sm text-gray-600">DNC Matches</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{results.safe_to_call}</div>
                  <div className="text-sm text-gray-600">Safe to Call</div>
                </div>
              </div>

              {/* Results Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left p-2 font-medium text-gray-700">Phone Number</th>
                      <th className="text-left p-2 font-medium text-gray-700">DNC Status</th>
                      <th className="text-left p-2 font-medium text-gray-700">Source</th>
                      <th className="text-left p-2 font-medium text-gray-700">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.data.slice(0, 10).map((row, index) => (
                      <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="p-2 font-mono">{row.phone_number}</td>
                        <td className="p-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                            row.is_dnc 
                              ? 'bg-red-100 text-red-800' 
                              : 'bg-green-100 text-green-800'
                          }`}>
                            {row.is_dnc ? (
                              <>
                                <XCircle className="h-3 w-3" />
                                DNC
                              </>
                            ) : (
                              <>
                                <CheckCircle className="h-3 w-3" />
                                Safe
                              </>
                            )}
                          </span>
                        </td>
                        <td className="p-2 text-gray-600">
                          {row.dnc_source || 'N/A'}
                        </td>
                        <td className="p-2 text-gray-600">
                          {row.notes || 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                {results.data.length > 10 && (
                  <div className="text-center mt-4 text-sm text-gray-500">
                    Showing first 10 results. Download full results for complete data.
                  </div>
                )}
              </div>

              <div className="mt-4 text-xs text-gray-500 text-center">
                Processed at: {new Date(results.processed_at).toLocaleString()}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  )
}
