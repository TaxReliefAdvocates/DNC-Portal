// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// API endpoints
export const API_ENDPOINTS = {
  PHONE_NUMBERS: `${API_BASE_URL}/api/v1/phone-numbers`,
  CRM_INTEGRATIONS: `${API_BASE_URL}/api/v1/crm`,
  CONSENT: `${API_BASE_URL}/api/v1/consent`,
  DNC_PROCESSING: `${API_BASE_URL}/api/v1/dnc`,
} as const

// Helper to extract demo auth headers from persisted store
function getDemoHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem('persist:do-not-call-root')
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const demoAuth = parsed.demoAuth ? JSON.parse(parsed.demoAuth) : null
    if (!demoAuth) return {}
    const { organizationId, userId, role } = demoAuth
    if (!organizationId || !userId || !role) return {}
    return {
      'X-Org-Id': String(organizationId),
      'X-User-Id': String(userId),
      'X-Role': String(role),
    }
  } catch {
    return {}
  }
}

// Helper function for API calls
export const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const response = await fetch(endpoint, {
    headers: {
      'Content-Type': 'application/json',
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




