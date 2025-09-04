import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { CRMStatus, CRMSystem } from '../../../types'
import { API_ENDPOINTS, apiCall } from '../../api'

interface CRMStatusState {
  crmStatuses: CRMStatus[]
  isLoading: boolean
  error: string | null
  demoTotal: number
  stats: {
    logics: { total: number, pending: number, processing: number, completed: number, failed: number },
    genesys: { total: number, pending: number, processing: number, completed: number, failed: number },
    ringcentral: { total: number, pending: number, processing: number, completed: number, failed: number },
    convoso: { total: number, pending: number, processing: number, completed: number, failed: number },
    ytel: { total: number, pending: number, processing: number, completed: number, failed: number },
  }
}

const initialState: CRMStatusState = {
  crmStatuses: [],
  isLoading: false,
  error: null,
  demoTotal: 0,
  stats: {
    logics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    genesys: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ringcentral: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    convoso: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ytel: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
  },
}

// Async thunks
export const fetchCRMStatuses = createAsyncThunk(
  'crmStatus/fetchAll',
  async (): Promise<CRMStatus[]> => {
    return apiCall(`${API_ENDPOINTS.CRM_INTEGRATIONS}/statuses`)
  }
)

export const fetchCRMStatusByPhone = createAsyncThunk(
  'crmStatus/fetchByPhone',
  async (phoneNumber: string): Promise<CRMStatus[]> => {
    return apiCall(`${API_ENDPOINTS.CRM_INTEGRATIONS}/status/${phoneNumber}`)
  }
)

export const retryCRMRemoval = createAsyncThunk(
  'crmStatus/retryRemoval',
  async ({ phoneNumberId, crmSystem }: { phoneNumberId: string; crmSystem: CRMSystem }): Promise<CRMStatus> => {
    return apiCall(`${API_ENDPOINTS.CRM_INTEGRATIONS}/retry-removal`, {
      method: 'POST',
      body: JSON.stringify({ phone_number_id: phoneNumberId, crm_system: crmSystem }),
    })
  }
)

const crmStatusSlice = createSlice({
  name: 'crmStatus',
  initialState,
  reducers: {
    updateCRMStatus: (state, action: PayloadAction<CRMStatus>) => {
      const index = state.crmStatuses.findIndex(
        status => status.id === action.payload.id
      )
      if (index !== -1) {
        state.crmStatuses[index] = action.payload
      } else {
        state.crmStatuses.push(action.payload)
      }
      // Update stats
      state.stats = calculateStats(state.crmStatuses)
    },
    addCRMStatus: (state, action: PayloadAction<CRMStatus>) => {
      state.crmStatuses.push(action.payload)
      state.stats = calculateStats(state.crmStatuses)
    },
    clearCRMStatuses: (state) => {
      state.crmStatuses = []
      state.stats = {
        logics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        genesys: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        ringcentral: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        convoso: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        ytel: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
      }
      state.demoTotal = 0
    },
    // Demo-mode helpers
    initDemoStats: (state, action: PayloadAction<number>) => {
      const total = action.payload
      const template = { total: 0, pending: total, processing: 0, completed: 0, failed: 0 }
      state.stats = {
        logics: { ...template },
        genesys: { ...template },
        ringcentral: { ...template },
        convoso: { ...template },
        ytel: { ...template },
      }
      state.demoTotal = total
    },
    setCRMStats: (
      state,
      action: PayloadAction<{ crm: CRMSystem; stats: { total: number; pending: number; processing: number; completed: number; failed: number } }>
    ) => {
      const { crm, stats } = action.payload
      // @ts-ignore - index by key
      state.stats[crm] = stats
    },
    clearDemoTotal: (state) => { state.demoTotal = 0 },
  },
  extraReducers: (builder) => {
    builder
      // Fetch CRM statuses
      .addCase(fetchCRMStatuses.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchCRMStatuses.fulfilled, (state, action) => {
        state.isLoading = false
        state.crmStatuses = action.payload
        state.stats = calculateStats(action.payload)
      })
      .addCase(fetchCRMStatuses.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'Failed to fetch CRM statuses'
      })
      
      // Fetch CRM status by phone
      .addCase(fetchCRMStatusByPhone.fulfilled, (state, action) => {
        // Merge with existing statuses
        action.payload.forEach(newStatus => {
          const index = state.crmStatuses.findIndex(
            existing => existing.id === newStatus.id
          )
          if (index !== -1) {
            state.crmStatuses[index] = newStatus
          } else {
            state.crmStatuses.push(newStatus)
          }
        })
        state.stats = calculateStats(state.crmStatuses)
      })
      
      // Retry CRM removal
      .addCase(retryCRMRemoval.fulfilled, (state, action) => {
        const index = state.crmStatuses.findIndex(
          status => status.id === action.payload.id
        )
        if (index !== -1) {
          state.crmStatuses[index] = action.payload
        }
        state.stats = calculateStats(state.crmStatuses)
      })
  },
})

// Helper function to calculate stats
function calculateStats(crmStatuses: CRMStatus[]) {
  const stats = {
    logics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    genesys: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ringcentral: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    convoso: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ytel: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
  }
  
  crmStatuses.forEach(status => {
    const system = status.crm_system
    if (stats[system]) {
      stats[system].total++
      stats[system][status.status as keyof typeof stats[typeof system]]++
    }
  })
  
  return stats
}

export const {
  updateCRMStatus,
  addCRMStatus,
  clearCRMStatuses,
  initDemoStats,
  setCRMStats,
} = crmStatusSlice.actions

export default crmStatusSlice.reducer
