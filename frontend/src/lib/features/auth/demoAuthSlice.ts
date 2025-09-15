import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export type DemoRole = 'owner' | 'admin' | 'member' | 'superadmin'

export interface DemoAuthState {
  organizationId: number
  userId: number
  role: DemoRole
}

const initialState: DemoAuthState = {
  organizationId: 1,
  userId: 1,
  role: 'member',
}

const demoAuthSlice = createSlice({
  name: 'demoAuth',
  initialState,
  reducers: {
    setRole(state, action: PayloadAction<DemoRole>) {
      state.role = action.payload
    },
    setOrganization(state, action: PayloadAction<number>) {
      state.organizationId = action.payload
    },
    setUser(state, action: PayloadAction<number>) {
      state.userId = action.payload
    },
    setSuperAdmin(state) {
      state.role = 'superadmin'
      state.userId = 1
      state.organizationId = 1
    }
  },
})

export const { setRole, setOrganization, setUser, setSuperAdmin } = demoAuthSlice.actions
export default demoAuthSlice.reducer


