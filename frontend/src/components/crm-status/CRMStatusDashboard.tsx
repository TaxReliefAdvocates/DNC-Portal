import React from 'react'
import { motion } from 'framer-motion'
import { 
  Phone, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Loader2, 
  RefreshCw,
  BarChart3,
  Building2,
  MessageSquare,
  Headphones,
  Zap
} from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAppSelector } from '@/lib/hooks'

// Updated CRM system types to match the new systems
type CRMSystem = 'logics' | 'genesys' | 'ringcentral' | 'convoso' | 'ytel'

interface StatusCardProps {
  title: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  count: number
  total: number
  icon: React.ReactNode
  onRetry?: () => void
  isLoading?: boolean
}

const StatusCard: React.FC<StatusCardProps> = ({
  title,
  status,
  count,
  total,
  icon,
  onRetry,
  isLoading = false,
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50 border-green-200'
      case 'failed':
        return 'text-red-600 bg-red-50 border-red-200'
      case 'processing':
        return 'text-blue-600 bg-blue-50 border-blue-200'
      case 'pending':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const getStatusIcon = (status: string, count: number) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5" />
      case 'failed':
        return <AlertCircle className="w-5 h-5" />
      case 'processing':
        return count > 0 ? <Loader2 className="w-5 h-5 animate-spin" /> : <Clock className="w-5 h-5" />
      case 'pending':
        return <Clock className="w-5 h-5" />
      default:
        return <Phone className="w-5 h-5" />
    }
  }

  const percentage = total > 0 ? Math.round((count / total) * 100) : 0

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Card className={`border-2 ${getStatusColor(status)} hover:shadow-md transition-shadow`}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {icon}
              <CardTitle className="text-lg font-semibold">{title}</CardTitle>
            </div>
            {getStatusIcon(status, count)}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">{count}</span>
              <span className="text-sm text-muted-foreground">
                {percentage}% of total
              </span>
            </div>
            
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  status === 'completed' ? 'bg-green-500' :
                  status === 'failed' ? 'bg-red-500' :
                  status === 'processing' ? 'bg-blue-500' :
                  'bg-yellow-500'
                }`}
                style={{ width: `${percentage}%` }}
              />
            </div>
            
            {onRetry && status === 'failed' && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Retrying...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Retry Failed
                  </>
                )}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export const CRMStatusDashboard: React.FC = () => {
  const { stats, isLoading, demoTotal } = useAppSelector((state) => state.crmStatus)
  const { phoneNumbers } = useAppSelector((state) => state.phoneNumbers)

  const totalPhoneNumbers = demoTotal || phoneNumbers.length

  // Updated CRM system display names
  const getCRMDisplayName = (crm: CRMSystem) => {
    switch (crm) {
      case 'logics':
        return 'Logics'
      case 'genesys':
        return 'Genesys'
      case 'ringcentral':
        return 'Ring Central'
      case 'convoso':
        return 'Convoso'
      case 'ytel':
        return 'Ytel'
      default:
        return crm
    }
  }

  // Updated CRM system icons
  const getCRMIcon = (crm: CRMSystem) => {
    switch (crm) {
      case 'logics':
        return <Building2 className="w-5 h-5" />
      case 'genesys':
        return <Headphones className="w-5 h-5" />
      case 'ringcentral':
        return <MessageSquare className="w-5 h-5" />
      case 'convoso':
        return <Zap className="w-5 h-5" />
      case 'ytel':
        return <Phone className="w-5 h-5" />
      default:
        return <Phone className="w-5 h-5" />
    }
  }

  const handleRetry = (crmSystem: CRMSystem) => {
    // TODO: Implement retry logic for failed removals
    console.log(`Retrying failed removals for ${crmSystem}`)
  }

  // Default stats for new CRM systems if they don't exist yet
  const defaultStats = {
    logics: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    genesys: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ringcentral: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    convoso: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 },
    ytel: { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 }
  }

  // Merge existing stats with default stats
  const mergedStats = { ...defaultStats, ...stats }

  const getPrimaryStatus = (crmStats: typeof defaultStats.logics) => {
    if (crmStats.failed > 0) return 'failed'
    if (crmStats.processing > 0) return 'processing'
    if (crmStats.pending > 0) return 'pending'
    if (crmStats.completed > 0) return 'completed'
    return 'completed' // Default to completed when no items exist
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">CRM Status Dashboard</h2>
        <div className="text-sm text-muted-foreground">
          Total Phone Numbers: {totalPhoneNumbers}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {Object.entries(mergedStats).map(([crmSystem, crmStats]) => (
          <StatusCard
            key={crmSystem}
            title={getCRMDisplayName(crmSystem as CRMSystem)}
            status={getPrimaryStatus(crmStats)}
            count={crmStats.total}
            total={totalPhoneNumbers}
            icon={getCRMIcon(crmSystem as CRMSystem)}
            onRetry={crmStats.failed > 0 ? () => handleRetry(crmSystem as CRMSystem) : undefined}
            isLoading={isLoading}
          />
        ))}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Processed</p>
                <p className="text-2xl font-bold">
                  {Object.values(mergedStats).reduce((sum, stat) => sum + stat.total, 0)}
                </p>
              </div>
              <BarChart3 className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Success Rate</p>
                <p className="text-2xl font-bold text-green-600">
                  {(() => {
                    const total = Object.values(mergedStats).reduce((sum, stat) => sum + stat.total, 0)
                    const completed = Object.values(mergedStats).reduce((sum, stat) => sum + stat.completed, 0)
                    return total > 0 ? Math.round((completed / total) * 100) : 0
                  })()}%
                </p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">In Progress</p>
                <p className="text-2xl font-bold text-blue-600">
                  {Object.values(mergedStats).reduce((sum, stat) => sum + stat.processing, 0)}
                </p>
              </div>
              {(() => {
                const processingCount = Object.values(mergedStats).reduce((sum, stat) => sum + stat.processing, 0)
                return processingCount > 0 ? (
                  <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                ) : (
                  <Clock className="w-8 h-8 text-blue-500" />
                )
              })()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Failed</p>
                <p className="text-2xl font-bold text-red-600">
                  {Object.values(mergedStats).reduce((sum, stat) => sum + stat.failed, 0)}
                </p>
              </div>
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
