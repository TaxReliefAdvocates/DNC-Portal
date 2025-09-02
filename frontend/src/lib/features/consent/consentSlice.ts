import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { Consent, ConsentType, ConsentStatus } from '../../../types'

interface ConsentState {
  consents: Consent[]
  isLoading: boolean
  error: string | null
  filters: {
    consent_type: ConsentType[]
    status: ConsentStatus[]
    search: string
  }
}

const initialState: ConsentState = {
  consents: [],
  isLoading: false,
  error: null,
  filters: {
    consent_type: [],
    status: [],
    search: '',
  },
}

// Async thunks
export const fetchConsents = createAsyncThunk(
  'consent/fetchAll',
  async (): Promise<Consent[]> => {
    const response = await fetch('/api/v1/consent')
    
    if (!response.ok) {
      throw new Error('Failed to fetch consents')
    }
    
    return response.json()
  }
)

export const fetchConsentByPhone = createAsyncThunk(
  'consent/fetchByPhone',
  async (phoneNumber: string): Promise<Consent[]> => {
    const response = await fetch(`/api/v1/consent/${phoneNumber}`)
    
    if (!response.ok) {
      throw new Error('Failed to fetch consent for phone number')
    }
    
    return response.json()
  }
)

export const updateConsent = createAsyncThunk(
  'consent/update',
  async (consent: Partial<Consent> & { id: string }): Promise<Consent> => {
    const response = await fetch(`/api/v1/consent/${consent.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(consent),
    })
    
    if (!response.ok) {
      throw new Error('Failed to update consent')
    }
    
    return response.json()
  }
)

export const addConsent = createAsyncThunk(
  'consent/add',
  async (consent: Omit<Consent, 'id'>): Promise<Consent> => {
    const response = await fetch('/api/v1/consent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(consent),
    })
    
    if (!response.ok) {
      throw new Error('Failed to add consent')
    }
    
    return response.json()
  }
)

const consentSlice = createSlice({
  name: 'consent',
  initialState,
  reducers: {
    setConsentTypeFilter: (state, action: PayloadAction<ConsentType[]>) => {
      state.filters.consent_type = action.payload
    },
    setConsentStatusFilter: (state, action: PayloadAction<ConsentStatus[]>) => {
      state.filters.status = action.payload
    },
    setConsentSearchFilter: (state, action: PayloadAction<string>) => {
      state.filters.search = action.payload
    },
    clearConsentFilters: (state) => {
      state.filters = {
        consent_type: [],
        status: [],
        search: '',
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch consents
      .addCase(fetchConsents.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchConsents.fulfilled, (state, action) => {
        state.isLoading = false
        state.consents = action.payload
      })
      .addCase(fetchConsents.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'Failed to fetch consents'
      })
      
      // Fetch consent by phone
      .addCase(fetchConsentByPhone.fulfilled, (state, action) => {
        // Merge with existing consents
        action.payload.forEach(newConsent => {
          const index = state.consents.findIndex(
            existing => existing.id === newConsent.id
          )
          if (index !== -1) {
            state.consents[index] = newConsent
          } else {
            state.consents.push(newConsent)
          }
        })
      })
      
      // Update consent
      .addCase(updateConsent.fulfilled, (state, action) => {
        const index = state.consents.findIndex(
          consent => consent.id === action.payload.id
        )
        if (index !== -1) {
          state.consents[index] = action.payload
        }
      })
      
      // Add consent
      .addCase(addConsent.fulfilled, (state, action) => {
        state.consents.push(action.payload)
      })
  },
})

export const {
  setConsentTypeFilter,
  setConsentStatusFilter,
  setConsentSearchFilter,
  clearConsentFilters,
} = consentSlice.actions

export default consentSlice.reducer

