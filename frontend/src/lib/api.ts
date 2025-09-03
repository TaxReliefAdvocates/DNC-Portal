// API Configuration
export const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000'

// API endpoints
export const API_ENDPOINTS = {
  PHONE_NUMBERS: `${API_BASE_URL}/api/v1/phone-numbers`,
  CRM_INTEGRATIONS: `${API_BASE_URL}/api/v1/crm`,
  CONSENT: `${API_BASE_URL}/api/v1/consent`,
  DNC_PROCESSING: `${API_BASE_URL}/api/v1/dnc`,
} as const

// Helper function for API calls
export const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const response = await fetch(endpoint, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    throw new Error(`API call failed: ${response.status} ${response.statusText}`)
  }

  return response.json()
}




