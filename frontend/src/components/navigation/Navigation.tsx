import React, { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../../lib/api'
import { Button } from '../ui/button'
import { Home, BarChart3, Settings, Phone, FileText } from 'lucide-react'
import { useAppSelector, useAppDispatch } from '../../lib/hooks'
import { setRole } from '../../lib/features/auth/demoAuthSlice'

interface NavigationProps {
  activeTab: 'main' | 'admin' | 'dnc-checker' | 'requests' | 'settings'
  onTabChange: (tab: 'main' | 'admin' | 'dnc-checker' | 'requests' | 'settings') => void
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const { role, organizationId, userId } = useAppSelector((s) => s.demoAuth)
  const dispatch = useAppDispatch()
  const isAdminComputed = (r: string) => r === 'admin' || r === 'superadmin'
  const isSuperAdminComputed = (r: string) => r === 'superadmin'
  const [resolvedRole, setResolvedRole] = useState<string>('')            // role from backend
  const [baseRole, setBaseRole] = useState<string>('')                    // immutable base role (from backend) for visibility
  const [overrideRole, setOverrideRole] = useState<string | null>(null)   // superadmin simulation
  const effectiveRole = overrideRole || baseRole || resolvedRole || role
  const isSuperAdmin = isSuperAdminComputed(effectiveRole)
  const isAdmin = isAdminComputed(effectiveRole)
  const [userLabel, setUserLabel] = useState<string>('')
  const initializedRef = useRef<boolean>(false)

  useEffect(() => {
    try {
      const msal = (window as any).__msalInstance
      const acct = msal?.getAllAccounts?.()[0]
      if (acct) setUserLabel(acct.name || acct.username || '')
    } catch {}
    ;(async()=>{
      if (initializedRef.current) return
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
        const scope = import.meta.env.VITE_ENTRA_SCOPE
        let token = ''
        if (acquire && scope) {
          token = await acquire([scope])
          if (token) {
            headers['Authorization'] = `Bearer ${token}`
          }
        }
        // Prefer backend-declared role
        const resp = await fetch(`${API_BASE_URL}/api/v1/tenants/auth/me`, { headers })
        if (resp.ok) {
          const j = await resp.json()
          const backendRole = String(j.role || '').toLowerCase()
          if (backendRole) {
            setResolvedRole(backendRole)
            if (!baseRole) setBaseRole(backendRole)
            if (backendRole !== role) { dispatch(setRole(backendRole as any)) }
            initializedRef.current = true
            return
          }
        }
        // Fallback: derive from token once
        if (token) {
          try {
            const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')))
            const rawRoles: string[] = Array.isArray(payload.roles) ? payload.roles.map((r: any)=>String(r).toLowerCase()) : []
            const normalized = new Set(rawRoles.map((s)=>s.replace(/[^a-z0-9]/g,'')))
            let derived = 'member'
            if (rawRoles.includes('all') || rawRoles.includes('superadmin') || normalized.has('superadmin')) {
              derived = 'superadmin'
            } else if (rawRoles.includes('owner') || normalized.has('owner')) {
              derived = 'owner'
            } else if (rawRoles.includes('approve_requests') || rawRoles.includes('admin') || normalized.has('admin')) {
              derived = 'admin'
            }
            setResolvedRole(derived)
            if (!baseRole) setBaseRole(derived)
            if (derived !== role) { dispatch(setRole(derived as any)) }
          } catch {}
        }
      } catch {}
      initializedRef.current = true
    })()
  }, [])

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-2">
              <Phone className="h-6 w-6 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">TRA DNC Portal</span>
            </div>
            
            <div className="flex space-x-1">
              <Button
                variant={activeTab === 'main' ? 'default' : 'ghost'}
                onClick={() => onTabChange('main')}
                className="flex items-center space-x-2"
              >
                <Home className="h-4 w-4" />
                <span>Main View</span>
              </Button>
              
              <Button
                variant={activeTab === 'dnc-checker' ? 'default' : 'ghost'}
                onClick={() => onTabChange('dnc-checker')}
                className="flex items-center space-x-2"
              >
                <FileText className="h-4 w-4" />
                <span>DNC Checker</span>
              </Button>
              
              {!isAdmin && (
                <Button
                  variant={activeTab === 'requests' ? 'default' : 'ghost'}
                  onClick={() => onTabChange('requests')}
                  className="flex items-center space-x-2"
                >
                  <FileText className="h-4 w-4" />
                  <span>My Requests</span>
                </Button>
              )}
              
              {isAdmin && (
                <Button
                  variant={activeTab === 'admin' ? 'default' : 'ghost'}
                  onClick={() => onTabChange('admin')}
                  className="flex items-center space-x-2"
                >
                  <BarChart3 className="h-4 w-4" />
                  <span>Admin</span>
                </Button>
              )}
              {isSuperAdmin && (
                <Button
                  variant={activeTab === 'settings' ? 'default' : 'ghost'}
                  onClick={() => onTabChange('settings')}
                  className="flex items-center space-x-2"
                >
                  <Settings className="h-4 w-4" />
                  <span>Settings</span>
                </Button>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* Only show role switcher if backend/base role is superadmin */}
            {baseRole === 'superadmin' && (
              <div className="flex items-center gap-2 text-sm text-gray-700">
                <span>Role:</span>
                <select
                  value={effectiveRole}
                  onChange={(e) => { const v = e.target.value as any; setOverrideRole(v); dispatch(setRole(v)); }}
                  className="border rounded px-2 py-1"
                >
                  {/* Match the three roles used in Azure and the backend */}
                  <option value="member">User</option>
                  <option value="admin">Admin</option>
                  <option value="superadmin">Super Admin</option>
                </select>
              </div>
            )}
            <div className="hidden sm:flex items-center text-sm text-gray-700 mr-2">
              {userLabel && <span className="mr-2 truncate max-w-[220px]" title={userLabel}>{userLabel}</span>}
              <span className="px-2 py-0.5 border rounded bg-gray-50">{effectiveRole}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={async ()=>{
                const scope = import.meta.env.VITE_ENTRA_SCOPE
                try {
                  const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
                  const msalLogout = (window as any).__msalLogout as ()=>Promise<void>
                  const msal = (window as any).__msalInstance
                  const hasAccount = (msal?.getAllAccounts?.() || []).length > 0
                  if (!hasAccount && acquire) {
                    await acquire([scope])
                    // refresh identity display
                    const acct = msal?.getAllAccounts?.()[0]
                    if (acct) setUserLabel(acct.name || acct.username || '')
                    const headers: Record<string, string> = { 'X-Role': String(role), 'X-Org-Id': String(organizationId), 'X-User-Id': String(userId) }
                    try {
                      const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
                      if (acquire && scope) {
                        const token = await acquire([scope])
                        if (token) headers['Authorization'] = `Bearer ${token}`
                      }
                    } catch {}
                    const me = await fetch(`${API_BASE_URL}/api/v1/tenants/auth/me`, { headers })
                    if (me.ok) { const j = await me.json(); setResolvedRole(j.role); if (j.role) dispatch(setRole(j.role as any)) }
                  } else if (hasAccount && msalLogout) {
                    await msalLogout()
                    setUserLabel('')
                    setResolvedRole('')
                  }
                } catch {
                  // ignore
                }
              }}
            >
              <Settings className="h-4 w-4 mr-2" />
              {(window as any).__msalInstance?.getAllAccounts?.().length ? 'Sign Out' : 'Sign In'}
            </Button>
          </div>
        </div>
      </div>
    </nav>
  )
}




