import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration: number
  timestamp: number
}

interface UIState {
  notifications: Notification[]
  isLoading: boolean
  error: string | null
  success: string | null
}

const initialState: UIState = {
  notifications: [],
  isLoading: false,
  error: null,
  success: null,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    addNotification: (state, action: PayloadAction<Omit<Notification, 'id' | 'timestamp'>>) => {
      const notification: Notification = {
        ...action.payload,
        id: Date.now().toString(),
        timestamp: Date.now(),
      }
      state.notifications.push(notification)
    },
    removeNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(
        notification => notification.id !== action.payload
      )
    },
    clearNotifications: (state) => {
      state.notifications = []
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload
    },
    setSuccess: (state, action: PayloadAction<string | null>) => {
      state.success = action.payload
    },
    clearMessages: (state) => {
      state.error = null
      state.success = null
    },
  },
})

export const {
  addNotification,
  removeNotification,
  clearNotifications,
  setLoading,
  setError,
  setSuccess,
  clearMessages,
} = uiSlice.actions

export default uiSlice.reducer
