import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { RefreshCw, Database, Users, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface SyncStats {
  total_dnc_entries: number;
  provider_stats: {
    [key: string]: {
      synced: number;
      failed: number;
      pending: number;
      total: number;
    };
  };
  recent_jobs: Array<{
    id: number;
    job_type: string;
    status: string;
    created_at: string;
    completed_at: string | null;
  }>;
}

interface SyncJob {
  id: number;
  job_type: string;
  status: string;
  total_entries: number;
  processed_entries: number;
  successful_syncs: number;
  failed_syncs: number;
  skipped_syncs: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

const getDemoHeaders = () => ({
  'X-Org-Id': '1',
  'X-User-Id': '1',
  'X-Role': 'admin'
});

export default function AdminSync() {
  const [stats, setStats] = useState<SyncStats | null>(null);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dnc-sync/stats`, {
        headers: getDemoHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Error fetching sync stats:', err);
    }
  };

  const fetchSyncJobs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dnc-sync/sync-jobs?limit=10`, {
        headers: getDemoHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setSyncJobs(data);
      }
    } catch (err) {
      console.error('Error fetching sync jobs:', err);
    }
  };

  const syncFromConvoso = async () => {
    setSyncing(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dnc-sync/sync-from-convoso`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getDemoHeaders()
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Refresh stats after a short delay
        setTimeout(() => {
          fetchStats();
          fetchSyncJobs();
        }, 2000);
      } else {
        setError('Failed to start sync from Convoso');
      }
    } catch (err) {
      setError('Error starting sync from Convoso');
    } finally {
      setSyncing(false);
    }
  };

  const syncToProviders = async () => {
    setSyncing(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dnc-sync/sync-to-providers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getDemoHeaders()
        },
        body: JSON.stringify({
          providers: ['ringcentral', 'genesys', 'ytel', 'logics']
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        // Refresh stats after a short delay
        setTimeout(() => {
          fetchStats();
          fetchSyncJobs();
        }, 2000);
      } else {
        setError('Failed to start sync to providers');
      }
    } catch (err) {
      setError('Error starting sync to providers');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchSyncJobs()]);
      setLoading(false);
    };
    
    loadData();
    
    // Refresh data every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-blue-100 text-blue-800',
      pending: 'bg-yellow-100 text-yellow-800'
    };
    
    return (
      <Badge className={variants[status as keyof typeof variants] || 'bg-gray-100 text-gray-800'}>
        {status}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading sync data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">DNC Sync Dashboard</h1>
        <div className="flex gap-2">
          <Button 
            onClick={syncFromConvoso} 
            disabled={syncing}
            className="flex items-center gap-2"
          >
            <Database className="h-4 w-4" />
            Sync from Convoso
          </Button>
          <Button 
            onClick={syncToProviders} 
            disabled={syncing}
            variant="outline"
            className="flex items-center gap-2"
          >
            <Users className="h-4 w-4" />
            Sync to Providers
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <XCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total DNC Entries</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_dnc_entries || 0}</div>
            <p className="text-xs text-muted-foreground">Master DNC list</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Sync Jobs</CardTitle>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {syncJobs.filter(job => job.status === 'running').length}
            </div>
            <p className="text-xs text-muted-foreground">Currently running</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Synced</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? Object.values(stats.provider_stats).reduce((sum, provider) => sum + provider.synced, 0) : 0}
            </div>
            <p className="text-xs text-muted-foreground">Across all providers</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed Syncs</CardTitle>
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? Object.values(stats.provider_stats).reduce((sum, provider) => sum + provider.failed, 0) : 0}
            </div>
            <p className="text-xs text-muted-foreground">Need attention</p>
          </CardContent>
        </Card>
      </div>

      {/* Provider Status */}
      <Card>
        <CardHeader>
          <CardTitle>Provider Sync Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {stats && Object.entries(stats.provider_stats).map(([provider, data]) => (
              <div key={provider} className="flex items-center justify-between p-4 border rounded-lg">
                <div className="flex items-center space-x-4">
                  <div className="font-medium capitalize">{provider}</div>
                  <div className="flex space-x-2">
                    <Badge variant="outline" className="text-green-600">
                      {data.synced} synced
                    </Badge>
                    <Badge variant="outline" className="text-red-600">
                      {data.failed} failed
                    </Badge>
                    <Badge variant="outline" className="text-yellow-600">
                      {data.pending} pending
                    </Badge>
                  </div>
                </div>
                <div className="w-32">
                  <Progress 
                    value={data.total > 0 ? (data.synced / data.total) * 100 : 0} 
                    className="h-2"
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Sync Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Sync Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {syncJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between p-4 border rounded-lg">
                <div className="flex items-center space-x-4">
                  {getStatusIcon(job.status)}
                  <div>
                    <div className="font-medium capitalize">{job.job_type.replace('_', ' ')}</div>
                    <div className="text-sm text-muted-foreground">
                      {job.processed_entries} / {job.total_entries} processed
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <div className="text-sm font-medium">
                      {job.successful_syncs} success, {job.failed_syncs} failed
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(job.created_at).toLocaleString()}
                    </div>
                  </div>
                  {getStatusBadge(job.status)}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
