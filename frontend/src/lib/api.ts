// API Configuration
const RAW_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
// In production builds served over HTTPS, force https base and disallow localhost fallback
const isHttpsPage = typeof window !== 'undefined' && window.location?.protocol === 'https:'
const isProd = import.meta.env.PROD
export const API_BASE_URL = (isProd && isHttpsPage)
  ? RAW_API_BASE_URL.replace(/^http:\/\//, 'https://')
  : RAW_API_BASE_URL

// API endpoints
export const API_ENDPOINTS = {
  PHONE_NUMBERS: `${API_BASE_URL}/api/v1/phone-numbers`,
  CRM_INTEGRATIONS: `${API_BASE_URL}/api/v1/crm`,
  CONSENT: `${API_BASE_URL}/api/v1/consent`,
  DNC_PROCESSING: `${API_BASE_URL}/api/v1/dnc`,
} as const

// Helper to extract demo auth headers from persisted store
export function getDemoHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem('persist:do-not-call-root')
    console.log('🔐 Raw localStorage data:', raw)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    console.log('🔐 Parsed localStorage:', parsed)
    const demoAuth = parsed.demoAuth ? JSON.parse(parsed.demoAuth) : null
    console.log('🔐 Demo auth data:', demoAuth)
    if (!demoAuth) return {}
    const { organizationId, userId, role } = demoAuth
    if (!organizationId || !userId || !role) return {}
    const headers = {
      'X-Org-Id': String(organizationId),
      'X-User-Id': String(userId),
      'X-Role': String(role),
    }
    console.log('🔐 Generated headers:', headers)
    return headers
  } catch (e) {
    console.log('🔐 Error getting demo headers:', e)
    return {}
  }
}

// Helper to get Azure AD token
let tokenInFlight: Promise<string | null> | null = null
async function getAzureToken(): Promise<string | null> {
  try {
    const acquire = (window as any).__msalAcquireToken as (scopes: string[]) => Promise<string>
    const scope = import.meta.env.VITE_ENTRA_SCOPE as string | undefined
    if (acquire && scope) {
      if (!tokenInFlight) tokenInFlight = acquire([scope]).catch(()=>null)
      const token = await tokenInFlight
      tokenInFlight = null
      return token || null
    }
  } catch (error) {
    console.warn('Failed to acquire Azure AD token:', error)
  }
  return null
}

// Helper function for API calls
export const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  // Get Azure AD token
  const token = await getAzureToken()
  let authHeaders: Record<string, string> = {}
  
  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(endpoint, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...getDemoHeaders(),
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    throw new Error(`API call failed: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

// Enhanced API call function with better error handling
export const authenticatedApiCall = async (endpoint: string, options: RequestInit = {}) => {
  const token = await getAzureToken()
  const demoHeaders = getDemoHeaders()
  
  if (!token && !demoHeaders['X-Org-Id']) {
    throw new Error('No authentication available')
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...demoHeaders,
  }

  // Merge additional headers if provided
  if (options.headers) {
    Object.assign(headers, options.headers)
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API call failed: ${response.status} ${response.statusText} - ${errorText}`)
  }

  return response.json()
}




