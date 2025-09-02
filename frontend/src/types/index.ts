// Phone Number Types
export interface PhoneNumber {
  id: string
  phone_number: string
  status: PhoneStatus
  created_at: string
  updated_at: string
  notes?: string
}

export type PhoneStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'

// CRM Integration Types
export interface CRMStatus {
  id: string
  phone_number_id: string
  crm_system: CRMSystem
  status: CRMStatusType
  response_data?: Record<string, any>
  processed_at?: string
  error_message?: string
  retry_count: number
}

export type CRMSystem = 'trackdrive' | 'irslogics' | 'listflex' | 'retriever' | 'everflow'
export type CRMStatusType = 'pending' | 'processing' | 'completed' | 'failed' | 'retry'

// Consent Types
export interface Consent {
  id: string
  phone_number_id: string
  consent_type: ConsentType
  status: ConsentStatus
  granted_at?: string
  revoked_at?: string
  source: string
  notes?: string
}

export type ConsentType = 'sms' | 'email' | 'phone' | 'marketing'
export type ConsentStatus = 'granted' | 'revoked' | 'pending' | 'expired'

// API Response Types
export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  errors?: string[]
}

export interface BulkPhoneNumberRequest {
  phone_numbers: string[]
  notes?: string
}

export interface BulkPhoneNumberResponse {
  success_count: number
  failed_count: number
  phone_numbers: PhoneNumber[]
  errors: string[]
}

// Report Types
export interface RemovalStats {
  total_processed: number
  successful_removals: number
  failed_removals: number
  pending_removals: number
  success_rate: number
  average_processing_time: number
}

export interface ProcessingTimeStats {
  crm_system: CRMSystem
  average_time: number
  min_time: number
  max_time: number
  total_requests: number
}

export interface ErrorRateStats {
  crm_system: CRMSystem
  error_count: number
  total_requests: number
  error_rate: number
  common_errors: string[]
}

// Form Types
export interface PhoneNumberFormData {
  phone_numbers: string
  notes?: string
}

export interface ConsentFormData {
  phone_number_id: string
  consent_type: ConsentType
  status: ConsentStatus
  source: string
  notes?: string
}

// UI State Types
export interface UIState {
  isLoading: boolean
  error: string | null
  success: string | null
}

export interface TableState {
  page: number
  pageSize: number
  sortBy: string
  sortOrder: 'asc' | 'desc'
  filters: Record<string, any>
}

// Filter Types
export interface PhoneNumberFilters {
  status?: PhoneStatus[]
  crm_system?: CRMSystem[]
  date_range?: {
    start: string
    end: string
  }
  search?: string
}

export interface ConsentFilters {
  consent_type?: ConsentType[]
  status?: ConsentStatus[]
  date_range?: {
    start: string
    end: string
  }
  search?: string
}
