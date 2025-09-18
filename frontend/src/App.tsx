import React, { useEffect, useState } from 'react'
import { API_BASE_URL } from './lib/api'
import { Provider } from 'react-redux'
import { PersistGate } from 'redux-persist/integration/react'
import { Toaster } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'

import { store, persistor } from './lib/store'
import { PhoneInput } from './components/phone-input/PhoneInput'
import { CRMStatusDashboard } from './components/crm-status/CRMStatusDashboard'
import { SystemsCheckPane } from './components/admin/SystemsCheckPane'
import { AdminDashboard } from './components/admin/AdminDashboard'
import { UserRequestHistory } from './components/admin/UserRequestHistory'
import { DNCChecker } from './components/dnc-checker/DNCChecker'
import { Navigation } from './components/navigation/Navigation'
import { SystemSettings } from './components/admin/SystemSettings'
import { Login } from './components/admin/Login'
import { useAppDispatch, useAppSelector } from './lib/hooks'
import { addBulkPhoneNumbers, fetchPhoneNumbers, resetLoadingState } from './lib/features/phoneNumbers/phoneNumbersSlice'
import { fetchCRMStatuses, initDemoStats, setCRMStats } from './lib/features/crmStatus/crmStatusSlice'
import { addNotification } from './lib/features/ui/uiSlice'

const getDemoHeaders = (): Record<string, string> => {
  try {
    const raw = localStorage.getItem('persist:do-not-call-root')
    if (!raw) return {}
    const state = JSON.parse(raw)
    const demoAuth = state.demoAuth ? JSON.parse(state.demoAuth) : null
    if (!demoAuth) return {}
    return {
      'X-Org-Id': String(demoAuth.organizationId),
      'X-User-Id': String(demoAuth.userId),
      'X-Role': String(demoAuth.role),
    }
  } catch {
    return {} as Record<string, string>
  }
}

const AppContent: React.FC = () => {
  const dispatch = useAppDispatch()
  const { isLoading, error } = useAppSelector((state) => state.phoneNumbers)
  const role = useAppSelector((s) => s.demoAuth.role)
  const [activeTab, setActiveTab] = useState<'main' | 'admin' | 'dnc-checker' | 'requests' | 'settings'>('main')
  const [rightPane, setRightPane] = useState<'none' | 'crm' | 'precheck' | 'systems'>('none')
  const [systemsNumbers, setSystemsNumbers] = useState<string[]>([])
  const [precheckResults] = useState<any | null>(null)
  const [precheckSelected, setPrecheckSelected] = useState<{ phone: string, cases: any[] } | null>(null)
  const [precheckLoading] = useState<boolean>(false)

  useEffect(() => {
    dispatch(resetLoadingState())
    const timer = setTimeout(() => {
      dispatch(resetLoadingState())
    }, 100)
    dispatch(fetchPhoneNumbers())
    dispatch(fetchCRMStatuses())
    return () => {
      clearTimeout(timer)
      dispatch(resetLoadingState())
    }
  }, [dispatch])

  const handlePhoneNumbersSubmit = async (numbers: string[], notes?: string) => {
    // Admin or Super Admin: run systems lookup and show actionable table, then let user "Push all"
    if (role === 'admin' || role === 'superadmin') {
      setSystemsNumbers(numbers)
      setRightPane('systems')
      dispatch(addNotification({ type: 'info', message: 'Checking systems… Use "Put on DNC List (all remaining)" to push.', duration: 5000 }))
      return
    }
    // Member fallback: keep previous flow (if ever enabled)
    try {
      const result = await dispatch(addBulkPhoneNumbers({ phone_numbers: numbers, notes })).unwrap()
      dispatch(addNotification({ type: 'success', message: `Successfully submitted ${result.success_count} phone numbers for removal`, duration: 5000 }))
      if (result.failed_count > 0) {
        dispatch(addNotification({ type: 'warning', message: `${result.failed_count} phone numbers failed validation`, duration: 5000 }))
      }
      const total = numbers.length
      dispatch(initDemoStats(total))
      const crms: Array<'logics' | 'genesys' | 'ringcentral' | 'convoso' | 'ytel'> = ['logics','genesys','ringcentral','convoso','ytel']
      let tick = 0
      setRightPane('crm')
      const interval = setInterval(() => {
        tick++
        crms.forEach((crm) => {
          const completed = Math.min(total, Math.round((tick / 5) * total))
          const failed = tick === 5 ? Math.floor(completed * 0.1) : 0
          const processing = tick < 5 ? Math.max(0, total - completed) : 0
          const pending = Math.max(0, total - completed - processing)
          dispatch(setCRMStats({ crm, stats: { total: completed, pending, processing, completed: completed - failed, failed } }))
        })
        if (tick >= 5) clearInterval(interval)
      }, 800)
      dispatch(resetLoadingState())
    } catch (error) {
      dispatch(addNotification({ type: 'error', message: 'Failed to submit phone numbers for removal', duration: 5000 }))
      dispatch(resetLoadingState())
    }
  }

  // Removed precheck helper from Admin flow to keep build clean

  const openPrecheckDetails = async (phone: string) => {
    try {
      setPrecheckSelected({ phone, cases: [] })
      const resp = await fetch(`${API_BASE_URL}/api/dnc/cases_by_phone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getDemoHeaders() },
        body: JSON.stringify({ phone_number: phone })
      })
    
      if (!resp.ok) {
        throw new Error('Failed to fetch details')
      }
      const json = await resp.json()
      setPrecheckSelected({ phone, cases: json.cases || [] })
    } catch (e) {
      dispatch(addNotification({ type: 'error', message: e instanceof Error ? e.message : 'Failed to fetch details', duration: 4000 }))
    }
  }

  const fmt = (v?: string) => {
    if (!v) return '—'
    const d = new Date(v)
    return isNaN(d.getTime()) ? '—' : d.toLocaleString()
  }

  const isTwoPane = rightPane !== 'none'

  const renderTabContent = () => {
    // Hard gate: require sign-in for the entire app and default to /login
    const msal = (window as any).__msalInstance
    const accounts = msal?.getAllAccounts?.() || []
    if (accounts.length === 0) {
      return <Login />
    }
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

            {/* Responsive container that centers when single-pane and expands when two-pane */}
            <div className={`${isTwoPane ? 'max-w-7xl' : 'max-w-3xl'} mx-auto w-full transition-all duration-300`}>
              <motion.div
                layout
                transition={{ duration: 0.35, ease: 'easeInOut' }}
                className={`grid gap-8 ${isTwoPane ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'} ${isTwoPane ? '' : 'justify-items-center'}`}
              >
                {/* Phone Input Section */}
                <motion.div
                  layout
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.1 }}
                  className={`${isTwoPane ? '' : 'w-full max-w-3xl'}`}
                >
                  <PhoneInput
                    onNumbersSubmit={handlePhoneNumbersSubmit}
                    isLoading={isLoading}
                  />
                </motion.div>

                {/* Right Pane (conditionally rendered) */}
                {isTwoPane && (
                  <motion.div
                    layout
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                  >
                    {rightPane === 'crm' && <CRMStatusDashboard />}
                    {rightPane === 'systems' && <SystemsCheckPane numbers={systemsNumbers} />}
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
              </motion.div>
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
          </>
        )
      case 'dnc-checker':
        return <DNCChecker />
      case 'requests':
        if (role === 'admin' || role === 'superadmin') {
          return (
            <div className="max-w-xl mx-auto p-6 mt-10 bg-white border rounded">
              <div className="text-lg font-semibold mb-2">No personal requests for admins</div>
              <div className="text-sm text-gray-600">Admins submit removals directly and review member requests on the Admin page.</div>
            </div>
          )
        }
        return (
          <div>
            <motion.h2 initial={{opacity:0,y:-10}} animate={{opacity:1,y:0}} className="text-2xl font-semibold mb-4">Your DNC Requests</motion.h2>
            <UserRequestHistory userId={1} />
          </div>
        )
      
      case 'admin':
        if (role === 'admin' || role === 'superadmin') return <AdminDashboard />
        return (
          <div className="max-w-xl mx-auto p-6 mt-10 bg-white border rounded">
            <div className="text-lg font-semibold mb-2">Admin access required</div>
            <div className="text-sm text-gray-600">Switch role to Admin in the top-right selector to view the Admin dashboard.</div>
          </div>
        )
      case 'settings':
        if (role === 'superadmin') {
          return (
            <div className="max-w-5xl mx-auto space-y-6">
              <h2 className="text-3xl font-bold">System Settings</h2>
              <SystemSettings />
            </div>
          )
        }
        return <Login />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="container mx-auto px-4 py-8">
        {renderTabContent()}
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
