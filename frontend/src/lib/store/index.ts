import { configureStore } from '@reduxjs/toolkit'
import { persistStore, persistReducer } from 'redux-persist'
import storage from 'redux-persist/lib/storage'
import { combineReducers } from '@reduxjs/toolkit'

import phoneNumbersReducer from '../features/phoneNumbers/phoneNumbersSlice'
import crmStatusReducer from '../features/crmStatus/crmStatusSlice'
import consentReducer from '../features/consent/consentSlice'
import uiReducer from '../features/ui/uiSlice'
import reportsReducer from '../features/reports/reportsSlice'

const persistConfig = {
  key: 'do-not-call-root',
  storage,
  whitelist: ['ui'], // Only persist UI state, not loading states
}

const rootReducer = combineReducers({
  phoneNumbers: phoneNumbersReducer,
  crmStatus: crmStatusReducer,
  consent: consentReducer,
  ui: uiReducer,
  reports: reportsReducer,
})

const persistedReducer = persistReducer(persistConfig, rootReducer)

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE'],
      },
    }),
})

export const persistor = persistStore(store)

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
