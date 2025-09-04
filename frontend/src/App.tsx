import React, { useEffect, useState } from 'react'
import { Provider } from 'react-redux'
import { PersistGate } from 'redux-persist/integration/react'
import { Toaster } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'

import { store, persistor } from './lib/store'
import { PhoneInput } from './components/phone-input/PhoneInput'
import { CRMStatusDashboard } from './components/crm-status/CRMStatusDashboard'
import { AdminDashboard } from './components/admin/AdminDashboard'
import { DNCChecker } from './components/dnc-checker/DNCChecker'
import { Navigation } from './components/navigation/Navigation'
import { useAppDispatch, useAppSelector } from './lib/hooks'
import { addBulkPhoneNumbers, fetchPhoneNumbers, resetLoadingState } from './lib/features/phoneNumbers/phoneNumbersSlice'
import { fetchCRMStatuses, initDemoStats, setCRMStats } from './lib/features/crmStatus/crmStatusSlice'
import { addNotification } from './lib/features/ui/uiSlice'

const AppContent: React.FC = () => {
  const dispatch = useAppDispatch()
  const { isLoading, error } = useAppSelector((state) => state.phoneNumbers)
  const [activeTab, setActiveTab] = useState<'main' | 'admin' | 'dnc-checker'>('main')
  const [rightPane, setRightPane] = useState<'none' | 'crm' | 'precheck'>('none')
  const [precheckResults, setPrecheckResults] = useState<any | null>(null)
  const [precheckSelected, setPrecheckSelected] = useState<{ phone: string, cases: any[] } | null>(null)
  const [precheckLoading, setPrecheckLoading] = useState<boolean>(false)

  useEffect(() => {
    // Reset loading state on mount and after a short delay to ensure it's cleared
    dispatch(resetLoadingState())
    
    const timer = setTimeout(() => {
      dispatch(resetLoadingState())
    }, 100)
    
    // Load initial data
    dispatch(fetchPhoneNumbers())
    dispatch(fetchCRMStatuses())
    
    // Cleanup function to reset loading state when component unmounts
    return () => {
      clearTimeout(timer)
      dispatch(resetLoadingState())
    }
  }, [dispatch])

  const handlePhoneNumbersSubmit = async (numbers: string[], notes?: string) => {
    try {
      const result = await dispatch(addBulkPhoneNumbers({ phone_numbers: numbers, notes })).unwrap()
      
      dispatch(addNotification({
        type: 'success',
        message: `Successfully submitted ${result.success_count} phone numbers for removal`,
        duration: 5000,
      }))

      if (result.failed_count > 0) {
        dispatch(addNotification({
          type: 'warning',
          message: `${result.failed_count} phone numbers failed validation`,
          duration: 5000,
        }))
      }
      
      // Demo-mode simulation of progress across CRMs
      const total = numbers.length
      dispatch(initDemoStats(total))
      const crms: Array<'logics' | 'genesys' | 'ringcentral' | 'convoso' | 'ytel'> = ['logics','genesys','ringcentral','convoso','ytel']
      // simulate over 5 ticks
      let tick = 0
      const interval = setInterval(() => {
        tick++
        crms.forEach((crm) => {
          const completed = Math.min(total, Math.round((tick / 5) * total))
          const failed = tick === 5 ? Math.floor(completed * 0.1) : 0 // 10% fail at end
          const processing = tick < 5 ? Math.max(0, total - completed) : 0
          const pending = Math.max(0, total - completed - processing)
          dispatch(setCRMStats({ crm, stats: { total: completed, pending, processing, completed: completed - failed, failed } }))
        })
        if (tick >= 5) clearInterval(interval)
      }, 800)

      // Show CRM status dashboard on the right
      setRightPane('crm')

      // Reset loading state after successful submission
      dispatch(resetLoadingState())
    } catch (error) {
      dispatch(addNotification({
        type: 'error',
        message: 'Failed to submit phone numbers for removal',
        duration: 5000,
      }))
      
      // Reset loading state after error
      dispatch(resetLoadingState())
    }
  }

  const handlePrecheck = async (numbers: string[]) => {
    try {
      setPrecheckResults(null)
      setPrecheckSelected(null)
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/check_batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_numbers: numbers }),
      })
      if (!resp.ok) {
        throw new Error('DNC pre-check failed')
      }
      const json = await resp.json()
      setPrecheckResults(json)
      setRightPane('precheck')
    } catch (e) {
      dispatch(addNotification({
        type: 'error',
        message: e instanceof Error ? e.message : 'DNC pre-check failed',
        duration: 4000,
      }))
    }
  }

  const openPrecheckDetails = async (phone: string) => {
    try {
      setPrecheckLoading(true)
      setPrecheckSelected({ phone, cases: [] })
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone })
      })
    
      if (!resp.ok) {
        throw new Error('Failed to fetch details')
      }
      const json = await resp.json()
      setPrecheckSelected({ phone, cases: json.cases || [] })
    } catch (e) {
      dispatch(addNotification({ type: 'error', message: e instanceof Error ? e.message : 'Failed to fetch details', duration: 4000 }))
    } finally {
      setPrecheckLoading(false)
    }
  }

  const fmt = (v?: string) => {
    if (!v) return '—'
    const d = new Date(v)
    return isNaN(d.getTime()) ? '—' : d.toLocaleString()
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'main':
        return (
          <>
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-center mb-8"
            >
              <h1 className="text-4xl font-bold text-gray-900 mb-2">
                TRA Do Not Call List Manager
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Manage phone number removals from Do Not Call lists across multiple CRM systems
              </p>
            </motion.div>

            {/* Keep a single PhoneInput instance mounted to preserve textarea contents */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Phone Input Section */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
              >
                <PhoneInput
                  onNumbersSubmit={handlePhoneNumbersSubmit}
                  onPrecheckDnc={handlePrecheck}
                  isLoading={isLoading}
                />
              </motion.div>

              {/* Right Pane (conditionally rendered) */}
              {rightPane !== 'none' && (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                >
                  {rightPane === 'crm' && <CRMStatusDashboard />}
                  {rightPane === 'precheck' && precheckResults && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-gray-900">{precheckResults.total_checked}</div>
                          <div className="text-sm text-gray-600">Total Checked</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-red-600">{precheckResults.dnc_matches}</div>
                          <div className="text-sm text-gray-600">DNC Matches</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-green-600">{precheckResults.safe_to_call}</div>
                          <div className="text-sm text-gray-600">Safe to Call</div>
                        </div>
                      </div>
                      <div className="max-h-60 overflow-y-auto space-y-2">
                        {precheckResults.results.slice(0, 20).map((r: any, i: number) => (
                          <div key={i} className={`p-2 rounded border text-sm ${r.is_dnc ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'} flex items-center justify-between`}>
                            <span className="font-medium">{r.phone_number}</span>
                            <span className={r.is_dnc ? 'text-red-700' : 'text-green-700'}>
                              {r.is_dnc ? ' DNC' : ' Safe'}
                            </span>
                            <button
                              className="ml-2 px-2 py-1 text-xs border rounded hover:bg-gray-50"
                              onClick={() => openPrecheckDetails(r.phone_number)}
                            >
                              View details
                            </button>
                          </div>
                        ))}
                      </div>
                      {precheckSelected && (
                        <div className="p-3 rounded border bg-white">
                          <div className="flex items-center justify-between">
                            <div className="font-medium">{precheckSelected.phone}</div>
                            <button className="text-xs text-gray-500 underline" onClick={() => setPrecheckSelected(null)}>Close</button>
                          </div>
                          {precheckLoading ? (
                            <div className="text-sm text-gray-600 mt-2">Loading details...</div>
                          ) : precheckSelected.cases.length ? (
                            <div className="mt-2 space-y-1 text-sm">
                              <div className="text-gray-700">Cases found: {precheckSelected.cases.length}</div>
                              <div className="max-h-40 overflow-y-auto divide-y">
                                {precheckSelected.cases.map((c: any, idx: number) => (
                                  <div key={idx} className="py-1 flex items-center justify-between">
                                    <div>
                                      <div className="text-gray-800">Case {c.CaseID}</div>
                                      <div className="text-xs text-gray-600">Created: {fmt(c.CreatedDate)} • Last Modified: {fmt(c.LastModifiedDate)}</div>
                                    </div>
                                    <div className="text-xs text-gray-700">{c.StatusName || `Status ${c.StatusID}`}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div className="text-sm text-gray-600 mt-2">No cases found for this number.</div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              )}
            </div>

            {/* Error Display */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="mt-8 p-4 bg-red-50 border border-red-200 rounded-lg"
                >
                  <div className="flex items-center gap-2 text-red-700">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span className="font-medium">Error:</span>
                    <span>{error}</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Debug: Reset Loading State Button */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-yellow-700">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <span className="font-medium">Loading state is stuck. Click to reset:</span>
                  </div>
                  <button
                    onClick={() => dispatch(resetLoadingState())}
                    className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700"
                  >
                    Reset Loading
                  </button>
                </div>
              </motion.div>
            )}
          </>
        )
      
      case 'dnc-checker':
        return <DNCChecker />
      
      case 'admin':
        return <AdminDashboard />
      
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
      
      <div className="container mx-auto px-4 py-8">
        {renderTabContent()}

        {/* Footer */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-16 text-center text-gray-500 text-sm"
        >
          <p>
            TRA Do Not Call List Management System • Built with React, TypeScript, and FastAPI
          </p>
        </motion.footer>
      </div>
    </div>
  )
}

const App: React.FC = () => {
  return (
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <AppContent />
        <Toaster
          position="top-right"
          richColors
          closeButton
          duration={5000}
        />
      </PersistGate>
    </Provider>
  )
}

export default App
