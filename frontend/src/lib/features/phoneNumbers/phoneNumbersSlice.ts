import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { PhoneNumber, PhoneStatus, BulkPhoneNumberRequest, BulkPhoneNumberResponse } from '../../../types'
import { API_ENDPOINTS, apiCall } from '../../api'

interface PhoneNumbersState {
  phoneNumbers: PhoneNumber[]
  isLoading: boolean
  error: string | null
  selectedPhoneNumbers: string[]
  filters: {
    status: PhoneStatus[]
    search: string
  }
}

const initialState: PhoneNumbersState = {
  phoneNumbers: [],
  isLoading: false,
  error: null,
  selectedPhoneNumbers: [],
  filters: {
    status: [],
    search: '',
  },
}

// Async thunks
export const addBulkPhoneNumbers = createAsyncThunk(
  'phoneNumbers/addBulk',
  async (request: BulkPhoneNumberRequest): Promise<BulkPhoneNumberResponse> => {
    return apiCall(`${API_ENDPOINTS.PHONE_NUMBERS}/bulk`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }
)

export const fetchPhoneNumbers = createAsyncThunk(
  'phoneNumbers/fetchAll',
  async (): Promise<PhoneNumber[]> => {
    return apiCall(API_ENDPOINTS.PHONE_NUMBERS)
  }
)

export const updatePhoneNumberStatus = createAsyncThunk(
  'phoneNumbers/updateStatus',
  async ({ id, status }: { id: string; status: PhoneStatus }): Promise<PhoneNumber> => {
    return apiCall(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    })
  }
)

const phoneNumbersSlice = createSlice({
  name: 'phoneNumbers',
  initialState,
  reducers: {
    setSelectedPhoneNumbers: (state, action: PayloadAction<string[]>) => {
      state.selectedPhoneNumbers = action.payload
    },
    togglePhoneNumberSelection: (state, action: PayloadAction<string>) => {
      const id = action.payload
      const index = state.selectedPhoneNumbers.indexOf(id)
      if (index > -1) {
        state.selectedPhoneNumbers.splice(index, 1)
      } else {
        state.selectedPhoneNumbers.push(id)
      }
    },
    clearSelection: (state) => {
      state.selectedPhoneNumbers = []
    },
    setStatusFilter: (state, action: PayloadAction<PhoneStatus[]>) => {
      state.filters.status = action.payload
    },
    setSearchFilter: (state, action: PayloadAction<string>) => {
      state.filters.search = action.payload
    },
    clearFilters: (state) => {
      state.filters = {
        status: [],
        search: '',
      }
    },
    resetLoadingState: (state) => {
      state.isLoading = false
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // Add bulk phone numbers
      .addCase(addBulkPhoneNumbers.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(addBulkPhoneNumbers.fulfilled, (state, action) => {
        state.isLoading = false
        state.phoneNumbers.push(...action.payload.phone_numbers)
      })
      .addCase(addBulkPhoneNumbers.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'Failed to add phone numbers'
      })
      
      // Fetch phone numbers
      .addCase(fetchPhoneNumbers.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchPhoneNumbers.fulfilled, (state, action) => {
        state.isLoading = false
        state.phoneNumbers = action.payload
      })
      .addCase(fetchPhoneNumbers.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'Failed to fetch phone numbers'
      })
      
      // Update phone number status
      .addCase(updatePhoneNumberStatus.fulfilled, (state, action) => {
        const index = state.phoneNumbers.findIndex(pn => pn.id === action.payload.id)
        if (index !== -1) {
          state.phoneNumbers[index] = action.payload
        }
      })
  },
})

export const {
  setSelectedPhoneNumbers,
  togglePhoneNumberSelection,
  clearSelection,
  setStatusFilter,
  setSearchFilter,
  clearFilters,
  resetLoadingState,
} = phoneNumbersSlice.actions

export default phoneNumbersSlice.reducer
