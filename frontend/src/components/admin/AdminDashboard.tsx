import React, { useEffect, useState } from 'react'
import { useAppDispatch, useAppSelector } from '../../lib/hooks'
import { fetchPhoneNumbers } from '../../lib/features/phoneNumbers/phoneNumbersSlice'
import { fetchCRMStatuses } from '../../lib/features/crmStatus/crmStatusSlice'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { API_BASE_URL } from '@/lib/api'
import { Button } from '../ui/button'
import { Phone, CheckCircle, XCircle, Clock, Database } from 'lucide-react'
import { AdminLitigation } from './AdminLitigation'
import { AdminSamplesGaps } from './AdminSamplesGaps'
import { AdminDncRequests } from './AdminDncRequests'
import { AdminSystemsCheck } from './AdminSystemsCheck'
import { AdminPropagationMonitor } from './AdminPropagationMonitor'
import { ApiEndpointTester } from './ApiEndpointTester'

export const AdminDashboard: React.FC = () => {
  const dispatch = useAppDispatch()
  const { phoneNumbers } = useAppSelector((state) => state.phoneNumbers)
  const { crmStatuses, stats } = useAppSelector((state) => state.crmStatus)
  const [activeTab, setActiveTab] = useState<'overview'|'pending'|'propagation'|'systems'|'litigation'|'samples'|'tester'>('pending')

  // Organization/user defaults (matches other admin panes)
  const organizationId = 1
  const adminUserId = 1

  // Summary metrics sourced from backend
  const [attemptSummary, setAttemptSummary] = useState<{ total: number; success: number; failed: number }>({ total: 0, success: 0, failed: 0 })
  const [dncEntriesCount, setDncEntriesCount] = useState<number>(0)
  const [loadingSummary, setLoadingSummary] = useState<boolean>(false)

  useEffect(() => {
    dispatch(fetchPhoneNumbers())
    dispatch(fetchCRMStatuses())
  }, [dispatch])
  // Acquire auth headers (Bearer if available + dev X- headers)
  const acquireAuthHeaders = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Org-Id': String(organizationId),
      'X-User-Id': String(adminUserId),
      'X-Role': 'superadmin',
    }
    try {
      const acquire = (window as any).__msalAcquireToken as (scopes: string[]) => Promise<string>
      const scope = (import.meta as any).env?.VITE_ENTRA_SCOPE as string | undefined
      if (acquire && scope) {
        const token = await acquire([scope])
        if (token) h['Authorization'] = `Bearer ${token}`
      }
    } catch {}
    return h
  }

  // Load small summary for the Overview cards from backend attempts and DNC entries
  const loadSummary = async () => {
    setLoadingSummary(true)
    try {
      const headers = await acquireAuthHeaders()
      // Fetch recent attempts (limit 200 for light payload)
      const a = await fetch(`${API_BASE_URL}/api/v1/tenants/propagation/attempts/${organizationId}?limit=200`, { headers })
      if (a.ok) {
        const attempts: Array<{ status: string }> = await a.json()
        const total = attempts.length
        const success = attempts.filter(t => t.status === 'success').length
        const failed = attempts.filter(t => t.status === 'failed').length
        setAttemptSummary({ total, success, failed })
      } else {
        setAttemptSummary({ total: 0, success: 0, failed: 0 })
      }
      // Fetch DNC entries to reflect total numbers in system (capped by API limit)
      const d = await fetch(`${API_BASE_URL}/api/v1/tenants/dnc-entries/${organizationId}`, { headers })
      if (d.ok) {
        const entries: unknown[] = await d.json()
        setDncEntriesCount(entries.length)
      } else {
        setDncEntriesCount(0)
      }
    } catch {
      setAttemptSummary({ total: 0, success: 0, failed: 0 })
      setDncEntriesCount(0)
    } finally {
      setLoadingSummary(false)
    }
  }

  useEffect(() => { loadSummary() }, [])

  const totalPhoneNumbers = phoneNumbers.length
  const totalCRMStatuses = crmStatuses.length

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
        <Button onClick={loadSummary} disabled={loadingSummary}>
          Refresh Data
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <nav className="flex flex-wrap gap-2 -mb-px text-sm">
          {[
            { key: 'pending', label: 'Pending' },
            { key: 'propagation', label: 'DNC History' },
            { key: 'systems', label: 'Systems Check' },
            { key: 'litigation', label: 'Litigation' },
            { key: 'samples', label: 'Samples & Gaps' },
            { key: 'overview', label: 'Overview' },
            { key: 'tester', label: 'Tester' },
          ].map(t => (
            <button
              key={t.key}
              className={`px-3 py-2 border-b-2 ${activeTab===t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-600 hover:text-gray-800'}`}
              onClick={()=>setActiveTab(t.key as any)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'pending' && (
        <AdminDncRequests organizationId={1} adminUserId={1} />
      )}

      {activeTab === 'propagation' && (
        <AdminPropagationMonitor organizationId={1} adminUserId={1} />
      )}

      {activeTab === 'systems' && (
        <AdminSystemsCheck />
      )}

      {activeTab === 'litigation' && (
        <AdminLitigation organizationId={1} adminUserId={1} />
      )}

      {activeTab === 'samples' && (
        <AdminSamplesGaps organizationId={1} adminUserId={1} />
      )}

      

      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Phone Numbers</CardTitle>
                <Phone className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dncEntriesCount || totalPhoneNumbers}</div>
                <p className="text-xs text-muted-foreground">
                  {loadingSummary ? 'Loading...' : 'Phone numbers in org DNC'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">CRM Status Records</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{attemptSummary.total || totalCRMStatuses}</div>
                <p className="text-xs text-muted-foreground">
                  {loadingSummary ? 'Loading...' : 'Provider attempts (recent)'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Completed Removals</CardTitle>
                <CheckCircle className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{attemptSummary.success}</div>
                <p className="text-xs text-muted-foreground">
                  Successfully pushed to providers (recent)
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Failed Removals</CardTitle>
                <XCircle className="h-4 w-4 text-red-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{attemptSummary.failed}</div>
                <p className="text-xs text-muted-foreground">
                  Failed provider attempts (recent)
                </p>
              </CardContent>
            </Card>
          </div>

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
        </div>
      )}

      {activeTab === 'tester' && (
        <ApiEndpointTester />
      )}
    </div>
  )
}
