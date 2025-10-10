import React, { useState, useRef } from 'react'
import { API_BASE_URL } from '../../lib/api'
import { motion } from 'framer-motion'
import { Upload, Download, FileText, AlertCircle, CheckCircle, X } from 'lucide-react'
import { Button } from '../ui/button'
import { RequestDNCModal } from './RequestDNCModal'
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
  
  // TPS (Logiqs) case lookups
  const [tpsPhone, setTpsPhone] = useState<string>('')
  const [tpsCasesResults, setTpsCasesResults] = useState<any[] | null>(null)
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [selectedCases, setSelectedCases] = useState<any[] | null>(null)
  const [isLoadingCases] = useState<boolean>(false)
  const [isCheckingTps, setIsCheckingTps] = useState<boolean>(false)

  // Local sub-tabs for methods (currently only systems check is used)
  const [activeTab] = useState<'quick' | 'systems' | 'tps' | 'csv'>('systems')
  
  // Systems check state
  const [systemsPhone, setSystemsPhone] = useState<string>('')
  const [systemsResult, setSystemsResult] = useState<any>(null)
  const [isCheckingSystems, setIsCheckingSystems] = useState<boolean>(false)
  const [expandedLogicsCases, setExpandedLogicsCases] = useState<boolean>(false)
  
  // DNC Request modal state
  const [showDncRequestModal, setShowDncRequestModal] = useState<boolean>(false)
  const [requestModalPhone, setRequestModalPhone] = useState<string>('')
  
  // Get user role to determine if Request DNC button should be shown
  const userRole = localStorage.getItem('role') || 'user'
  const isAdmin = ['admin', 'superadmin', 'owner'].includes(userRole)

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
      
      const response = await fetch(`${API_BASE_URL}/api/dnc/process`, {
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
      const downloadUrl = `${API_BASE_URL}/api/dnc${result.file}`
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
      const response = await fetch(`${API_BASE_URL}/api/dnc/check_number`, {
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
      
      const response = await fetch(`${API_BASE_URL}/api/dnc/check_batch`, {
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
  
  const findTpsCases = async () => {
    if (!tpsPhone.trim()) return
    setIsCheckingTps(true)
    setError(null)
    setTpsCasesResults(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: tpsPhone.trim() })
      })
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to fetch TPS cases')
      }
      const data = await response.json()
      setTpsCasesResults(data.cases || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch TPS cases')
    } finally {
      setIsCheckingTps(false)
    }
  }

  // Removed unused openNumberDetails; using precheck detail flow instead

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
      const response = await fetch(`${API_BASE_URL}/api/dnc/run_automation`, {
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

  const checkSystems = async () => {
    if (!systemsPhone.trim()) return
    setIsCheckingSystems(true)
    setError(null)
    setSystemsResult(null)
    setExpandedLogicsCases(false)
    
    const providers: Record<string, any> = {}
    
    try {
      // 1) FreeDNC API check
      try {
        const fj = await fetch(`${API_BASE_URL}/api/check_number`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (fj.ok) {
          const fjData = await fj.json()
          providers.dnc = { listed: Boolean(fjData?.is_dnc) }
        }
      } catch {}

      // 2) RingCentral search for number
      try {
        const rc = await fetch(`${API_BASE_URL}/api/v1/ringcentral/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (rc.ok) {
          const rj = await rc.json()
          const isOnDnc = rj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.ringcentral = { listed: null, status: 'unknown' }
          } else {
            providers.ringcentral = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 3) Convoso search-dnc
      try {
        const cv = await fetch(`${API_BASE_URL}/api/v1/convoso/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (cv.ok) {
          const cj = await cv.json()
          const isOnDnc = cj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.convoso = { listed: null, status: 'unknown' }
          } else {
            providers.convoso = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 4) Ytel search-dnc (two-step DNC check)
      try {
        const yt = await fetch(`${API_BASE_URL}/api/v1/ytel/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (yt.ok) {
          const yj = await yt.json()
          const isOnDnc = yj?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.ytel = { listed: null, status: 'unknown' }
          } else {
            providers.ytel = { listed: isOnDnc || false }
          }
        }
      } catch {}

      // 5) Logics search-by-phone
      try {
        const lj = await fetch(`${API_BASE_URL}/api/v1/logics/search-by-phone`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (lj.ok) {
          const ljData = await lj.json()
          // Logics returns cases in data.raw_response.Data
          const cases = ljData?.data?.raw_response?.Data || []
          providers.logics = { 
            listed: cases.length > 0, 
            count: cases.length, 
            cases: cases 
          }
        }
      } catch {}

      // 6) Genesys search-dnc
      try {
        const gj = await fetch(`${API_BASE_URL}/api/v1/genesys/search-dnc`, { 
          method:'POST', 
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone_number: systemsPhone })
        })
        if (gj.ok) {
          const gjData = await gj.json()
          const isOnDnc = gjData?.data?.is_on_dnc
          if (isOnDnc === null) {
            providers.genesys = { listed: null, status: 'unknown' }
          } else {
            providers.genesys = { listed: isOnDnc || false }
          }
        }
      } catch {}

      setSystemsResult({ phone_number: systemsPhone, providers })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed systems check')
    } finally {
      setIsCheckingSystems(false)
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
    setSystemsPhone('')
    setSystemsResult(null)
    setError(null)
    setProcessingStatus('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const cell = (listed?: boolean | null, extra?: string) => {
    if (listed === true) return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">On DNC</span>
    if (listed === false) return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Not Listed</span>
    return <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown{extra ? ` • ${extra}` : ''}</span>
  }

  const openDncRequestModal = (_phoneNumber: string) => {
    setRequestModalPhone(_phoneNumber || systemsPhone || '')
    setShowDncRequestModal(true)
  }

  const closeDncRequestModal = () => {
    setShowDncRequestModal(false)
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
          Check DNC status across all CRM systems (RingCentral, Convoso, Ytel, Logics, Genesys) 
          to ensure compliance and avoid calling restricted numbers.
        </p>
      </motion.div>

      {/* Sub-tabs - Only Systems Check visible for now */}
      {/* <div className="flex justify-center gap-2">
        <Button variant={activeTab === 'quick' ? 'default' : 'outline'} onClick={() => setActiveTab('quick')}>Quick Check</Button>
        <Button variant={activeTab === 'systems' ? 'default' : 'outline'} onClick={() => setActiveTab('systems')}>Systems Check</Button>
        <Button variant={activeTab === 'tps' ? 'default' : 'outline'} onClick={() => setActiveTab('tps')}>TPS Cases</Button>
        <Button variant={activeTab === 'csv' ? 'default' : 'outline'} onClick={() => setActiveTab('csv')}>CSV Upload</Button>
      </div> */}

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
              {activeTab === 'quick' ? 'Quick Phone Number Check' : 
               activeTab === 'systems' ? 'Systems Check' : 'TPS2 Database Check'}
            </h3>
            <p className="text-gray-600">
              {activeTab === 'quick'
                ? 'Check individual phone numbers or batches without CSV upload'
                : activeTab === 'systems'
                ? 'Check DNC status across all CRM systems (RingCentral, Convoso, Ytel, Logics, Genesys)'
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

            {activeTab === 'systems' && (
            <>
            {/* Systems Check */}
            <div className="space-y-3">
              <Label htmlFor="systems-phone">Phone Number</Label>
              <div className="flex gap-2">
                <Input
                  id="systems-phone"
                  type="tel"
                  placeholder="Enter phone number (e.g., 5173715410)"
                  value={systemsPhone}
                  onChange={(e) => setSystemsPhone(e.target.value)}
                  className="flex-1"
                />
                <Button 
                  onClick={checkSystems} 
                  disabled={!systemsPhone.trim() || isCheckingSystems}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {isCheckingSystems ? 'Checking...' : 'Check All Systems'}
                </Button>
              </div>
              
              {/* Systems Result */}
              {systemsResult && (
                <div className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm">
                      <span className="font-medium">{systemsResult.phone_number}</span>
                      {isCheckingSystems && <span className="text-xs text-gray-500"> • Checking…</span>}
                    </div>
                    <div className="text-xs text-gray-500">{new Date().toLocaleTimeString()}</div>
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    {/* National DNC */}
                    <div className="flex items-center justify-between border rounded p-2">
                      <div className="font-medium">National DNC</div>
                      <div className="flex items-center gap-2">
                        {cell(systemsResult.providers?.dnc?.listed)}
                      </div>
                    </div>
                    
                    {/* RingCentral */}
                    <div className="flex items-center justify-between border rounded p-2">
                      <div className="font-medium">RingCentral</div>
                      <div className="flex items-center gap-2">
                        {cell(systemsResult.providers?.ringcentral?.listed)}
                      </div>
                    </div>
                    
                    {/* Convoso */}
                    <div className="flex items-center justify-between border rounded p-2">
                      <div className="font-medium">Convoso</div>
                      <div className="flex items-center gap-2">
                        {cell(systemsResult.providers?.convoso?.listed)}
                      </div>
                    </div>
                    
                    {/* Logics (TPS) */}
                    <div className="border rounded p-2">
                      <div className="flex items-center justify-between">
                        <div className="font-medium">Logics (TPS)</div>
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-2">
                            {systemsResult.providers?.logics ? (
                              systemsResult.providers.logics.listed ? (
                                <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Active Case</span>
                              ) : (
                                <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">No Cases</span>
                              )
                            ) : (
                              <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Unknown</span>
                            )}
                            {typeof systemsResult.providers?.logics?.count === 'number' && (
                              <span className="text-xs text-gray-600">{systemsResult.providers.logics.count} case(s)</span>
                            )}
                          </div>
                          {systemsResult.providers?.logics?.cases && systemsResult.providers.logics.cases.length > 0 && (
                            <button
                              onClick={() => setExpandedLogicsCases(!expandedLogicsCases)}
                              className="text-xs text-blue-600 hover:text-blue-800 underline"
                            >
                              {expandedLogicsCases ? 'Hide Details' : 'Show Details'}
                            </button>
                          )}
                        </div>
                      </div>
                      
                      {/* Case Details Dropdown */}
                      {expandedLogicsCases && systemsResult.providers?.logics?.cases && systemsResult.providers.logics.cases.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          <div className="text-xs text-gray-600 mb-2">Case Details:</div>
                          <div className="space-y-1">
                            {systemsResult.providers.logics.cases.map((caseItem: any, index: number) => (
                              <div key={index} className="bg-gray-50 p-2 rounded text-xs">
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <span className="font-medium text-gray-700">Case ID:</span>
                                    <span className="ml-1 text-gray-900">{caseItem.CaseID || 'N/A'}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium text-gray-700">Status ID:</span>
                                    <span className="ml-1 text-gray-900">{caseItem.StatusID || 'N/A'}</span>
                                  </div>
                                  <div className="col-span-2">
                                    <span className="font-medium text-gray-700">Name:</span>
                                    <span className="ml-1 text-gray-900">
                                      {[caseItem.FirstName, caseItem.MiddleName, caseItem.LastName]
                                        .filter(Boolean)
                                        .join(' ') || 'N/A'}
                                    </span>
                                  </div>
                                  {caseItem.Email && (
                                    <div className="col-span-2">
                                      <span className="font-medium text-gray-700">Email:</span>
                                      <span className="ml-1 text-gray-900">{caseItem.Email}</span>
                                    </div>
                                  )}
                                  {caseItem.CreatedDate && (
                                    <div className="col-span-2">
                                      <span className="font-medium text-gray-700">Created:</span>
                                      <span className="ml-1 text-gray-900">{new Date(caseItem.CreatedDate).toLocaleString()}</span>
                                    </div>
                                  )}
                                  {caseItem.TaxAmount && (
                                    <div className="col-span-2">
                                      <span className="font-medium text-gray-700">Tax Amount:</span>
                                      <span className="ml-1 text-gray-900">${caseItem.TaxAmount.toLocaleString()}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Ytel */}
                    <div className="flex items-center justify-between border rounded p-2">
                      <div className="font-medium">Ytel</div>
                      <div className="flex items-center gap-2">
                        {cell(systemsResult.providers?.ytel?.listed)}
                      </div>
                    </div>
                    
                    {/* Genesys */}
                    <div className="flex items-center justify-between border rounded p-2">
                      <div className="font-medium">Genesys</div>
                      <div className="flex items-center gap-2">
                        {cell(systemsResult.providers?.genesys?.listed)}
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-3 flex items-center justify-between">
                    <div className="text-xs text-gray-600">
                      <div>
                        <strong>Note:</strong> This shows DNC status across all systems. 
                        {isAdmin ? ' You can add numbers to DNC lists directly from the Admin Dashboard.' : ' Only admins can add numbers to DNC lists.'}
                      </div>
                    </div>
                    {!isAdmin && (
                      <Button 
                        onClick={() => openDncRequestModal(systemsResult.phone_number)}
                        className="bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2"
                      >
                        Request DNC
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
            </>
            )}

            {activeTab === 'tps' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="tps-phone">TPS (Logiqs) Cases</Label>
              </div>
              <div className="flex gap-2 items-center">
                <Input id="tps-phone" type="tel" placeholder="Enter phone number" value={tpsPhone} onChange={(e)=>setTpsPhone(e.target.value)} className="flex-1" />
                <Button onClick={findTpsCases} disabled={isCheckingTps} className="bg-purple-600 hover:bg-purple-700">
                  {isCheckingTps ? 'Finding cases…' : 'Find cases'}
                </Button>
              </div>
              {tpsCasesResults && (
                <div className="space-y-2">
                  <div className="text-sm text-gray-700">Found {tpsCasesResults.length} case(s)</div>
                  <div className="max-h-60 overflow-y-auto divide-y border rounded">
                    {tpsCasesResults.map((c: any, idx: number)=> (
                      <div key={idx} className="p-2 text-sm flex items-center justify-between">
                        <div>
                          <div className="font-medium">Case {c.CaseID}</div>
                          <div className="text-xs text-gray-600">Created: {formatDateTime(c.CreatedDate)} | Last Modified: {formatDateTime(c.LastModifiedDate)}</div>
                        </div>
                        <div className="text-xs text-gray-700">{c.StatusName || `Status ${c.StatusID}`}</div>
                      </div>
                    ))}
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

      {/* DNC Request Modal */}
      {showDncRequestModal && (
        <RequestDNCModal 
          organizationId={Number(localStorage.getItem('org_id') || '1')} 
          onClose={closeDncRequestModal}
          phoneNumber={requestModalPhone}
        />
      )}
    </div>
  )
}
