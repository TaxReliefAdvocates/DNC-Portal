import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { CRMStatus, CRMSystem, CRMStatusType } from '../../../types'
import { API_ENDPOINTS, apiCall } from '../../api'

interface CRMStatusState {
  crmStatuses: CRMStatus[]
  isLoading: boolean
  error: string | null
  stats: {
    trackdrive: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    irslogics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    listflex: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    retriever: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    everflow: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
  }
}

const initialState: CRMStatusState = {
  crmStatuses: [],
  isLoading: false,
  error: null,
  stats: {
    trackdrive: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    irslogics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    listflex: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    retriever: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    everflow: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
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
        trackdrive: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        irslogics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        listflex: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        retriever: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
        everflow: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
      }
    },
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
    trackdrive: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    irslogics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    listflex: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    retriever: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    everflow: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
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
} = crmStatusSlice.actions

export default crmStatusSlice.reducer
