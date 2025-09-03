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
import { fetchCRMStatuses } from './lib/features/crmStatus/crmStatusSlice'
import { addNotification } from './lib/features/ui/uiSlice'

const AppContent: React.FC = () => {
  const dispatch = useAppDispatch()
  const { isLoading, error } = useAppSelector((state) => state.phoneNumbers)
  const [activeTab, setActiveTab] = useState<'main' | 'admin' | 'dnc-checker'>('main')

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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Phone Input Section */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
              >
                <PhoneInput
                  onNumbersSubmit={handlePhoneNumbersSubmit}
                  isLoading={isLoading}
                />
              </motion.div>

              {/* CRM Status Dashboard */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
              >
                <CRMStatusDashboard />
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
