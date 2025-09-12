import React from 'react'
import { Button } from '../ui/button'
import { Home, BarChart3, Settings, Phone, FileText } from 'lucide-react'
import { useAppSelector, useAppDispatch } from '../../lib/hooks'
import { setRole } from '../../lib/features/auth/demoAuthSlice'

interface NavigationProps {
  activeTab: 'main' | 'admin' | 'dnc-checker' | 'requests' | 'settings'
  onTabChange: (tab: 'main' | 'admin' | 'dnc-checker' | 'requests' | 'settings') => void
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const { role } = useAppSelector((s) => s.demoAuth)
  const dispatch = useAppDispatch()
  const isAdmin = role === 'admin' || role === 'owner'
  const isSuperAdmin = role === 'superadmin'

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
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <span>Role:</span>
              <select
                value={role}
                onChange={(e) => dispatch(setRole(e.target.value as any))}
                className="border rounded px-2 py-1"
                disabled={!isSuperAdmin}
              >
                <option value="member">User</option>
                <option value="admin">Admin</option>
                <option value="owner">Owner</option>
                <option value="superadmin">System Admin</option>
              </select>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={async ()=>{
                const scope = import.meta.env.VITE_ENTRA_SCOPE
                try {
                  const acquire = (window as any).__msalAcquireToken as (scopes: string[])=>Promise<string>
                  if (acquire) {
                    await acquire([scope])
                    alert('Signed in successfully')
                  } else {
                    alert('Auth not initialized')
                  }
                } catch (e) {
                  alert('Login failed')
                }
              }}
            >
              <Settings className="h-4 w-4 mr-2" />
              Sign In
            </Button>
          </div>
        </div>
      </div>
    </nav>
  )
}




