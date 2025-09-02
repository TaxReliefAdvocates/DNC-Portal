import React from 'react'
import { Button } from '../ui/button'
import { Home, BarChart3, Settings, Phone } from 'lucide-react'

interface NavigationProps {
  activeTab: 'main' | 'admin'
  onTabChange: (tab: 'main' | 'admin') => void
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-2">
              <Phone className="h-6 w-6 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">DNC Manager</span>
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
                variant={activeTab === 'admin' ? 'default' : 'ghost'}
                onClick={() => onTabChange('admin')}
                className="flex items-center space-x-2"
              >
                <BarChart3 className="h-4 w-4" />
                <span>Admin Dashboard</span>
              </Button>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <Button variant="outline" size="sm">
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Button>
          </div>
        </div>
      </div>
    </nav>
  )
}



