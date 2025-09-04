import React, { useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../../lib/hooks'
import { fetchPhoneNumbers } from '../../lib/features/phoneNumbers/phoneNumbersSlice'
import { fetchCRMStatuses } from '../../lib/features/crmStatus/crmStatusSlice'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Phone, CheckCircle, XCircle, Clock, Database } from 'lucide-react'
import { AdminLitigation } from './AdminLitigation'
import { AdminDncRequests } from './AdminDncRequests'

export const AdminDashboard: React.FC = () => {
  const dispatch = useAppDispatch()
  const { phoneNumbers, isLoading: phoneNumbersLoading } = useAppSelector((state) => state.phoneNumbers)
  const { crmStatuses, stats, isLoading: crmLoading } = useAppSelector((state) => state.crmStatus)

  useEffect(() => {
    dispatch(fetchPhoneNumbers())
    dispatch(fetchCRMStatuses())
  }, [dispatch])

  const totalPhoneNumbers = phoneNumbers.length
  const totalCRMStatuses = crmStatuses.length

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'text-green-600'
      case 'failed':
        return 'text-red-600'
      case 'processing':
        return 'text-yellow-600'
      case 'pending':
        return 'text-blue-600'
      default:
        return 'text-gray-600'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'processing':
        return <Clock className="w-4 h-4 text-yellow-600" />
      case 'pending':
        return <Clock className="w-4 h-4 text-blue-600" />
      default:
        return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="text-gray-600 mt-2">Monitor phone number removals and CRM system status</p>
        </div>
        <Button onClick={() => window.location.reload()}>
          Refresh Data
        </Button>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Phone Numbers</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalPhoneNumbers}</div>
            <p className="text-xs text-muted-foreground">
              {phoneNumbersLoading ? 'Loading...' : 'Phone numbers in system'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CRM Status Records</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCRMStatuses}</div>
            <p className="text-xs text-muted-foreground">
              {crmLoading ? 'Loading...' : 'CRM removal attempts'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed Removals</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {crmStatuses.filter(s => s.status === 'completed').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Successfully removed from CRM systems
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed Removals</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {crmStatuses.filter(s => s.status === 'failed').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Failed removal attempts
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Pending DNC Requests */}
      <AdminDncRequests organizationId={1} adminUserId={1} />

      {/* TCPA Litigation */}
      <AdminLitigation organizationId={1} adminUserId={1} />

      {/* CRM System Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Logics Statistics</CardTitle>
            <CardDescription>Removal status for Logics CRM</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.logics).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="capitalize">{status}</span>
                  </div>
                  <span className="font-semibold">{count as number}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Genesys Statistics</CardTitle>
            <CardDescription>Removal status for Genesys CRM</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.genesys).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="capitalize">{status}</span>
                  </div>
                  <span className="font-semibold">{count as number}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ring Central Statistics</CardTitle>
            <CardDescription>Removal status for Ring Central CRM</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.ringcentral).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="capitalize">{status}</span>
                  </div>
                  <span className="font-semibold">{count as number}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Convoso Statistics</CardTitle>
            <CardDescription>Removal status for Convoso CRM</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.convoso).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="capitalize">{status}</span>
                  </div>
                  <span className="font-semibold">{count as number}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ytel Statistics</CardTitle>
            <CardDescription>Removal status for Ytel CRM</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.ytel).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="capitalize">{status}</span>
                  </div>
                  <span className="font-semibold">{count as number}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Phone Numbers */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Phone Numbers</CardTitle>
          <CardDescription>Latest phone numbers added to the system</CardDescription>
        </CardHeader>
        <CardContent>
          {phoneNumbersLoading ? (
            <div className="text-center py-4">Loading phone numbers...</div>
          ) : phoneNumbers.length === 0 ? (
            <div className="text-center py-4 text-gray-500">No phone numbers found</div>
          ) : (
            <div className="space-y-3">
              {phoneNumbers.slice(0, 10).map((phone) => (
                <div key={phone.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">{phone.phone_number}</div>
                    <div className="text-sm text-gray-500">
                      Added: {new Date(phone.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(phone.status)}`}>
                      {phone.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent CRM Status Updates */}
      <Card>
        <CardHeader>
          <CardTitle>Recent CRM Status Updates</CardTitle>
          <CardDescription>Latest CRM removal attempts and their status</CardDescription>
        </CardHeader>
        <CardContent>
          {crmLoading ? (
            <div className="text-center py-4">Loading CRM statuses...</div>
          ) : crmStatuses.length === 0 ? (
            <div className="text-center py-4 text-gray-500">No CRM status records found</div>
          ) : (
            <div className="space-y-3">
              {crmStatuses.slice(0, 10).map((status) => (
                <div key={status.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">Phone ID: {status.phone_number_id}</div>
                    <div className="text-sm text-gray-500">
                      {status.crm_system} • {new Date().toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status.status)}
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(status.status)}`}>
                      {status.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
