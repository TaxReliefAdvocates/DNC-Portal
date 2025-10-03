import React, { useEffect, useState } from 'react'
import { API_BASE_URL } from '../../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'

interface SearchHistoryItem {
  id: number
  user_id: number
  organization_id: number | null
  phone_number: string
  search_results: any
  created_at: string
}

const getDemoHeaders = (): Record<string, string> => {
  try {
    const raw = localStorage.getItem('persist:do-not-call-root')
    if (!raw) return {}
    const state = JSON.parse(raw)
    const demoAuth = state.demoAuth ? JSON.parse(state.demoAuth) : null
    if (!demoAuth) return {}
    return {
      'X-Org-Id': String(demoAuth.organizationId),
      'X-User-Id': String(demoAuth.userId),
      'X-Role': demoAuth.role || 'admin',
      'Authorization': `Bearer ${demoAuth.token || 'demo-token'}`
    }
  } catch {
    return {}
  }
}

interface Props {
  onPhoneSelect?: (phone: string) => void
}

export const RecentSearches: React.FC<Props> = ({ onPhoneSelect }) => {
  const [searches, setSearches] = useState<SearchHistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchRecentSearches = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/search-history/recent?limit=10&user_id=1&organization_id=1&role=user`, {
        headers: getDemoHeaders()
      })
      
      if (response.ok) {
        const data = await response.json()
        setSearches(data)
      }
    } catch (error) {
      console.error('Failed to fetch recent searches:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRecentSearches()
  }, [])

  const formatTime = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  const getStatusBadge = (providers: any) => {
    const anyListed = Object.values(providers).some((p: any) => p?.listed === true)
    if (anyListed) {
      return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-800">On DNC</span>
    } else {
      return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Clear</span>
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Searches</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-gray-500">Loading...</div>
        </CardContent>
      </Card>
    )
  }

  if (searches.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Searches</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-gray-500">No recent searches found</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Searches</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {searches.map((search) => (
            <div
              key={search.id}
              className="flex items-center justify-between p-2 border rounded hover:bg-gray-50 cursor-pointer"
              onClick={() => onPhoneSelect?.(search.phone_number)}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{search.phone_number}</span>
                  {search.search_results?.providers && getStatusBadge(search.search_results.providers)}
                </div>
                <div className="text-xs text-gray-500">
                  {formatTime(search.created_at)}
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation()
                  onPhoneSelect?.(search.phone_number)
                }}
              >
                Re-check
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
