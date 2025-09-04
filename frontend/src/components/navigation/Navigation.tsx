import React from 'react'
import { Button } from '../ui/button'
import { Home, BarChart3, Settings, Phone, FileText } from 'lucide-react'

interface NavigationProps {
  activeTab: 'main' | 'admin' | 'dnc-checker'
  onTabChange: (tab: 'main' | 'admin' | 'dnc-checker') => void
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
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
              
              <Button
                variant={activeTab === 'admin' ? 'default' : 'ghost'}
                onClick={() => onTabChange('admin')}
                className="flex items-center space-x-2"
              >
                <BarChart3 className="h-4 w-4" />
                <span>Admin: Requests</span>
              </Button>
              <Button variant="ghost" onClick={() => onTabChange('admin')} className="text-gray-700">Admin: DNC List</Button>
              <Button variant="ghost" onClick={() => onTabChange('admin')} className="text-gray-700">Admin: SMS STOPs</Button>
              <Button variant="ghost" onClick={() => onTabChange('admin')} className="text-gray-700">Admin: Samples</Button>
              <Button variant="ghost" onClick={() => onTabChange('admin')} className="text-gray-700">Admin: Services</Button>
              <Button variant="ghost" onClick={() => onTabChange('admin')} className="text-gray-700">Admin: Access</Button>
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




