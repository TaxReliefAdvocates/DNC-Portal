import React, { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload, Download, FileText, AlertCircle, CheckCircle, X, Eye } from 'lucide-react'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'





interface FreeDNCApiResponse {
  success: boolean
  file: string
  processing_id: string
}

export const DNCChecker: React.FC = () => {
  const [file, setFile] = useState<File | null>(null)
  const [columnIndex, setColumnIndex] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [freeDncResults, setFreeDncResults] = useState<any[] | null>(null)
  const [processingStatus, setProcessingStatus] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // Single/Batch phone number checking
  const [singlePhone, setSinglePhone] = useState<string>('')
  const [batchPhones, setBatchPhones] = useState<string>('')
  const [singleResult, setSingleResult] = useState<any>(null)
  const [batchResults, setBatchResults] = useState<any>(null)
  const [isCheckingSingle, setIsCheckingSingle] = useState<boolean>(false)
  const [isCheckingBatch, setIsCheckingBatch] = useState<boolean>(false)
  
  // TPS2 Database checking
  const [tpsLimit, setTpsLimit] = useState<number>(1000)
  const [tpsResults, setTpsResults] = useState<any>(null)
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [selectedCases, setSelectedCases] = useState<any[] | null>(null)
  const [isLoadingCases, setIsLoadingCases] = useState<boolean>(false)
  const [isCheckingTps, setIsCheckingTps] = useState<boolean>(false)
  const [tpsConnectionStatus, setTpsConnectionStatus] = useState<string>('')

  // Local sub-tabs for methods
  const [activeTab, setActiveTab] = useState<'quick' | 'tps' | 'csv'>('quick')

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0]
    if (selectedFile && selectedFile.type === 'text/csv') {
      setFile(selectedFile)
      setError(null)
    } else {
      setError('Please select a valid CSV file')
    }
  }

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault()
  }

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault()
    const droppedFile = event.dataTransfer.files[0]
    if (droppedFile && droppedFile.type === 'text/csv') {
      setFile(droppedFile)
      setError(null)
    } else {
      setError('Please drop a valid CSV file')
    }
  }

  const processFile = async () => {
    if (!file) return

    setIsProcessing(true)
    setError(null)
    setProcessingStatus('Uploading CSV file...')

    try {
      // Step 1: Upload CSV to FreeDNCList.com API endpoint
      const formData = new FormData()
      formData.append('file', file)
      formData.append('column_index', columnIndex.toString())
      formData.append('format', 'json')

      setProcessingStatus('Processing CSV with DNC checking...')
      
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/process`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to process file')
      }

      const result: FreeDNCApiResponse = await response.json()
      console.log('API Response:', result)
      setProcessingStatus('Downloading processed results...')

      // Step 2: Download the processed CSV file
      const downloadUrl = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc${result.file}`
      console.log('Downloading from:', downloadUrl)
      const csvResponse = await fetch(downloadUrl)
      
      if (!csvResponse.ok) {
        throw new Error('Failed to download processed file')
      }

      const csvText = await csvResponse.text()
      
      // Step 3: Parse CSV and convert to JSON format
      const csvData = parseCSVToJSON(csvText)
      setFreeDncResults(csvData)
      
      setProcessingStatus('Processing complete!')
      
      // CSV processing complete
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setProcessingStatus('')
    } finally {
      setIsProcessing(false)
    }
  }

  const parseCSVToJSON = (csvText: string): any[] => {
    const lines = csvText.split('\n')
    if (lines.length < 2) return []
    
    const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''))
    const data = []
    
    for (let i = 1; i < lines.length; i++) {
      if (lines[i].trim()) {
        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''))
        const row: any = {}
        
        headers.forEach((header, index) => {
          row[header] = values[index] || ''
        })
        
        data.push(row)
      }
    }
    
    return data
  }

  const downloadResults = () => {
    if (!freeDncResults) return

    const csvContent = [
      Object.keys(freeDncResults[0]),
      ...freeDncResults.map(row => Object.values(row))
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

  const checkSingleNumber = async () => {
    if (!singlePhone.trim()) return
    
    setIsCheckingSingle(true)
    setError(null)
    setSingleResult(null)
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/check_number`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone_number: singlePhone.trim() }),
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to check phone number')
      }
      
      const result = await response.json()
      setSingleResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsCheckingSingle(false)
    }
  }
  
  const checkBatchNumbers = async () => {
    if (!batchPhones.trim()) return
    
    setIsCheckingBatch(true)
    setError(null)
    setBatchResults(null)
    
    try {
      // Parse phone numbers (comma, newline, or space separated)
      const phoneNumbers = batchPhones
        .split(/[,\n\s]+/)
        .map(p => p.trim())
        .filter(p => p.length > 0)
      
      if (phoneNumbers.length === 0) {
        throw new Error('No valid phone numbers found')
      }
      
      if (phoneNumbers.length > 1000) {
        throw new Error('Maximum 1000 phone numbers per batch')
      }
      
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/check_batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone_numbers: phoneNumbers }),
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to check batch phone numbers')
      }
      
      const result = await response.json()
      setBatchResults(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsCheckingBatch(false)
    }
  }
  
  const testTpsConnection = async () => {
    try {
      setTpsConnectionStatus('Testing connection...')
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/test_tps_connection`)
      
      if (!response.ok) {
        throw new Error('Failed to test connection')
      }
      
      const result = await response.json()
      if (result.connected) {
        setTpsConnectionStatus('✅ Connected to TPS2 database')
      } else {
        setTpsConnectionStatus('❌ Connection failed')
      }
    } catch (err) {
      setTpsConnectionStatus('❌ Connection test failed')
      setError(err instanceof Error ? err.message : 'Connection test failed')
    }
  }
  
  const checkTpsDatabase = async () => {
    setIsCheckingTps(true)
    setError(null)
    setTpsResults(null)
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/check_tps_database`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ limit: tpsLimit }),
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to check TPS2 database')
      }
      
      const result = await response.json()
      setTpsResults(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsCheckingTps(false)
    }
  }

  const openNumberDetails = async (phoneNumber: string, caseId?: number) => {
    try {
      setSelectedNumber(phoneNumber)
      setIsLoadingCases(true)
      setSelectedCases(null)
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phoneNumber, case_id: caseId })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch cases')
      }
      const data = await response.json()
      setSelectedCases(data.cases || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch number details')
    } finally {
      setIsLoadingCases(false)
    }
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return '—'
    try {
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) return '—'
      return d.toLocaleString()
    } catch {
      return '—'
    }
  }

  const runAutomation = async () => {
    if (!selectedNumber) return
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/run_automation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: selectedNumber })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Automation failed to start')
      }
      // No-op for now; toast could be added later
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Automation failed')
    }
  }
  
  const resetForm = () => {
    setFile(null)
    setColumnIndex(0)
    setFreeDncResults(null)
    setSinglePhone('')
    setBatchPhones('')
    setSingleResult(null)
    setBatchResults(null)
    setTpsLimit(1000)
    setTpsResults(null)
    setTpsConnectionStatus('')
    setError(null)
    setProcessingStatus('')
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
          Upload a CSV file to check phone numbers against Do Not Call lists using FreeDNCList.com API. 
          Ensure compliance across all CRM systems.
        </p>
      </motion.div>

      {/* Sub-tabs */}
      <div className="flex justify-center gap-2">
        <Button variant={activeTab === 'quick' ? 'default' : 'outline'} onClick={() => setActiveTab('quick')}>Quick Check</Button>
        <Button variant={activeTab === 'tps' ? 'default' : 'outline'} onClick={() => setActiveTab('tps')}>TPS Cases</Button>
        <Button variant={activeTab === 'csv' ? 'default' : 'outline'} onClick={() => setActiveTab('csv')}>CSV Upload</Button>
      </div>

      {/* Single/Batch Phone Number Checking Section OR TPS (switch by tab) */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="space-y-6"
      >
        <Card>
          <CardHeader>
            <h3 className="text-xl font-semibold text-gray-900">
              {activeTab === 'quick' ? 'Quick Phone Number Check' : 'TPS2 Database Check'}
            </h3>
            <p className="text-gray-600">
              {activeTab === 'quick'
                ? 'Check individual phone numbers or batches without CSV upload'
                : 'Find possible DNC matches from TPS and view case details'}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {activeTab === 'quick' && (
            <>
            {/* Single Phone Number Check */}
            <div className="space-y-3">
              <Label htmlFor="single-phone">Single Phone Number</Label>
              <div className="flex gap-2">
                <Input
                  id="single-phone"
                  type="tel"
                  placeholder="Enter phone number (e.g., 5173715410)"
                  value={singlePhone}
                  onChange={(e) => setSinglePhone(e.target.value)}
                  className="flex-1"
                />
                <Button 
                  onClick={checkSingleNumber} 
                  disabled={!singlePhone.trim() || isCheckingSingle}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {isCheckingSingle ? 'Checking...' : 'Check'}
                </Button>
              </div>
              
              {/* Single Result */}
              {singleResult && (
                <div className={`p-3 rounded-lg border ${
                  singleResult.is_dnc 
                    ? 'bg-red-50 border-red-200 text-red-800' 
                    : 'bg-green-50 border-green-200 text-green-800'
                }`}>
                  <div className="font-medium">
                    {singleResult.phone_number}: {singleResult.is_dnc ? 'Yes - On DNC List' : 'No - Not on DNC'}
                  </div>
                  <div className="text-sm opacity-75">{singleResult.notes}</div>
                </div>
              )}
            </div>
            
            {/* Batch Phone Numbers Check */}
            <div className="space-y-3">
              <Label htmlFor="batch-phones">Batch Phone Numbers</Label>
              <div className="space-y-2">
                <Textarea
                  id="batch-phones"
                  placeholder="Enter phone numbers separated by commas, spaces, or new lines&#10;Example:&#10;5173715410&#10;555-000-1234&#10;555-111-5678"
                  value={batchPhones}
                  onChange={(e) => setBatchPhones(e.target.value)}
                  rows={4}
                  className="font-mono text-sm"
                />
                <Button 
                  onClick={checkBatchNumbers} 
                  disabled={!batchPhones.trim() || isCheckingBatch}
                  className="bg-blue-600 hover:bg-blue-700 w-full"
                >
                  {isCheckingBatch ? 'Checking...' : `Check ${batchPhones.split(/[,\n\s]+/).filter(p => p.trim()).length} Numbers`}
                </Button>
              </div>
              
              {/* Batch Results */}
              {batchResults && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 p-3 bg-gray-50 rounded-lg">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-gray-900">{batchResults.total_checked}</div>
                      <div className="text-sm text-gray-600">Total Checked</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-600">{batchResults.dnc_matches}</div>
                      <div className="text-sm text-gray-600">DNC Matches</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">{batchResults.safe_to_call}</div>
                      <div className="text-sm text-gray-600">Safe to Call</div>
                    </div>
                  </div>
                  
                  <div className="max-h-60 overflow-y-auto space-y-2">
                    {batchResults.results.map((result: any, index: number) => (
                      <div key={index} className={`p-2 rounded border text-sm ${
                        result.is_dnc 
                          ? 'bg-red-50 border-red-200' 
                          : 'bg-green-50 border-green-200'
                      }`}>
                        <span className="font-medium">{result.phone_number}</span>: 
                        <span className={result.is_dnc ? 'text-red-700' : 'text-green-700'}>
                          {result.is_dnc ? ' DNC' : ' Safe'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            </>
            )}

            {activeTab === 'tps' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="tps-limit">TPS2 Database Check</Label>
                <Button onClick={testTpsConnection} size="sm" variant="outline" className="text-xs">Test Connection</Button>
              </div>
              {tpsConnectionStatus && (
                <div className={`text-sm p-2 rounded ${
                  tpsConnectionStatus.includes('✅') 
                    ? 'bg-green-50 text-green-700 border border-green-200' 
                    : tpsConnectionStatus.includes('❌')
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-blue-50 text-blue-700 border border-blue-200'
                }`}>{tpsConnectionStatus}</div>
              )}
              <div className="flex gap-2 items-center">
                <Label htmlFor="tps-limit" className="text-sm">Limit:</Label>
                <Input id="tps-limit" type="number" min="1" max="10000" value={tpsLimit} onChange={(e) => setTpsLimit(parseInt(e.target.value) || 1000)} className="w-24" />
                <span className="text-sm text-gray-500">(max 10,000)</span>
              </div>
              <Button onClick={checkTpsDatabase} disabled={isCheckingTps} className="bg-purple-600 hover:bg-purple-700 w-full">
                {isCheckingTps ? 'Checking TPS2 Database...' : `Run DNC Check on ${tpsLimit} Numbers`}
              </Button>
              {tpsResults && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-4 p-3 bg-purple-50 rounded-lg border border-purple-200">
                    <div className="text-center"><div className="text-2xl font-bold text-gray-900">{tpsResults.total_checked}</div><div className="text-sm text-gray-600">Total Checked</div></div>
                    <div className="text-center"><div className="text-2xl font-bold text-red-600">{tpsResults.dnc_matches}</div><div className="text-sm text-gray-600">DNC Matches</div></div>
                    <div className="text-center"><div className="text-2xl font-bold text-green-600">{tpsResults.safe_to_call}</div><div className="text-sm text-gray-600">Safe to Call</div></div>
                  </div>
                  <div className="text-sm text-gray-600 text-center">{tpsResults.message}</div>
                  <div className="max-h-60 overflow-y-auto space-y-2">
                    {tpsResults.results.slice(0, 20).map((result: any, index: number) => (
                      <div key={index} className={`p-2 rounded border text-sm ${result.is_dnc ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                        <div className="flex justify-between items-start">
                          <div>
                            <button className="font-medium underline hover:text-blue-700" onClick={() => openNumberDetails(result.PhoneNumber, result.CaseID)}>{result.PhoneNumber}</button>
                            <span className={result.is_dnc ? 'text-red-700' : 'text-green-700'}>{result.is_dnc ? ' DNC' : ' Safe'}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{result.PhoneType}</span>
                            <button className="inline-flex items-center gap-1 px-2 py-1 rounded border hover:bg-gray-50" title="View details" onClick={() => openNumberDetails(result.PhoneNumber, result.CaseID)}>
                              <Eye className="h-3 w-3" />
                              <span>View</span>
                            </button>
                          </div>
                        </div>
                        <div className="text-xs text-gray-600 mt-1">Case: {result.CaseID} | {result.dnc_notes}</div>
                      </div>
                    ))}
                    {tpsResults.results.length > 20 && (<div className="text-center text-sm text-gray-500 py-2">Showing first 20 results. Total: {tpsResults.results.length}</div>)}
                  </div>
                </div>
              )}
            </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Number Detail Drawer/Section */}
      {activeTab === 'tps' && selectedNumber && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-purple-700">{selectedNumber}</CardTitle>
                <div className="flex gap-2">
                  <Button onClick={runAutomation} className="bg-red-600 hover:bg-red-700">RUN DNC Automation</Button>
                  <Button variant="outline" onClick={() => { setSelectedNumber(null); setSelectedCases(null); }}>Close</Button>
                </div>
              </div>
              <CardDescription>All cases for this number with created/last modified/status.</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingCases ? (
                <div className="text-sm text-gray-600">Loading cases...</div>
              ) : (
                <div className="space-y-2">
                  {selectedCases && selectedCases.length > 0 ? (
                    <div className="max-h-60 overflow-y-auto divide-y border rounded">
                      {selectedCases.map((c: any, idx: number) => (
                        <div key={idx} className="p-2 text-sm flex items-center justify-between">
                          <div>
                            <div className="font-medium">Case {c.CaseID}</div>
                            <div className="text-xs text-gray-600">
                              Created: {formatDateTime(c.CreatedDate)} | Last Modified: {formatDateTime(c.LastModifiedDate)}
                            </div>
                          </div>
                          <div className="text-xs text-gray-700">
                            {c.StatusName || `Status ${c.StatusID}`} • {c.PhoneType}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-gray-600">No cases found for this number.</div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* File Upload Section */}
      {activeTab === 'csv' && (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
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
                file ? 'bg-blue-50' : 'bg-gray-50'
              }`}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="space-y-2">
                <Upload className="h-12 w-12 mx-auto text-gray-400" />
                <p className="text-sm text-gray-600">
                  {file ? `Selected: ${file.name}` : 'Click to select or drag and drop CSV file'}
                </p>
                <p className="text-xs text-gray-500">Only CSV files are supported</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
      )}

      {/* Column Index Selection */}
      {activeTab === 'csv' && (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-blue-600">Phone Number Column</CardTitle>
            <CardDescription>
              Specify which column contains the phone numbers (0-based index)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4">
              <Label htmlFor="columnIndex">Column Index:</Label>
              <Input
                id="columnIndex"
                type="number"
                min="0"
                value={columnIndex}
                onChange={(e) => setColumnIndex(parseInt(e.target.value) || 0)}
                className="w-20"
              />
              <span className="text-sm text-gray-500">
                (0 = first column, 1 = second column, etc.)
              </span>
            </div>
          </CardContent>
        </Card>
      </motion.div>
      )}

      {/* Process Button */}
      {activeTab === 'csv' && (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-center"
      >
        <Button
          onClick={processFile}
          disabled={!file || isProcessing}
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 text-lg"
        >
          {isProcessing ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
              Processing...
            </>
          ) : (
            <>
              <FileText className="h-5 w-5 mr-2" />
              Process DNC Check
            </>
          )}
        </Button>
      </motion.div>
      )}

      {/* Processing Status */}
      {activeTab === 'csv' && processingStatus && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <div className="inline-flex items-center px-4 py-2 bg-blue-100 text-blue-800 rounded-lg">
            <CheckCircle className="h-4 w-4 mr-2" />
            {processingStatus}
          </div>
        </motion.div>
      )}

      {/* Error Display */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center p-4 bg-red-100 border border-red-300 rounded-lg"
        >
          <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
          <span className="text-red-700">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setError(null)}
            className="ml-auto text-red-500 hover:text-red-700"
          >
            <X className="h-4 w-4" />
          </Button>
        </motion.div>
      )}

      {/* Results Display */}
      {activeTab === 'csv' && freeDncResults && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="space-y-4"
        >
          {/* Summary Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-green-600">Processing Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{freeDncResults.length}</div>
                  <div className="text-sm text-gray-600">Total Records</div>
                </div>
                <div className="p-4 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {freeDncResults.filter(row => row.DNC_Status === 'DNC_MATCH').length}
                  </div>
                  <div className="text-sm text-red-600">DNC Matches</div>
                </div>
                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {freeDncResults.filter(row => row.DNC_Status === 'SAFE').length}
                  </div>
                  <div className="text-sm text-green-600">Safe to Call</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Download Button */}
          <div className="text-center">
            <Button
              onClick={downloadResults}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              <Download className="h-4 w-4 mr-2" />
              Download Results CSV
            </Button>
          </div>

          {/* JSON Results Display */}
          <Card>
            <CardHeader>
              <CardTitle className="text-blue-600">Results in JSON Format</CardTitle>
              <CardDescription>
                Processed data from FreeDNCList.com API
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-auto max-h-96">
                <pre className="text-sm">
                  {JSON.stringify(freeDncResults, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>

          {/* Reset Button */}
          <div className="text-center">
            <Button
              onClick={resetForm}
              variant="outline"
              className="border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Process Another File
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  )
}
