// Domain types mirroring phase5/api/schemas.py exactly.
// Keep in sync with the backend contract — do not invent fields.

export type UserRole = 'CITIZEN' | 'ANALYST' | 'ADMIN'

export type EventType =
  | 'RAINFALL'
  | 'THUNDERSTORM'
  | 'FLOODING'
  | 'HEATWAVE'
  | 'FOG'
  | 'DUST_STORM'
  | 'STRONG_WIND'
  | 'OTHER'

export const EVENT_TYPES: EventType[] = [
  'RAINFALL',
  'THUNDERSTORM',
  'FLOODING',
  'HEATWAVE',
  'FOG',
  'DUST_STORM',
  'STRONG_WIND',
  'OTHER',
]

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME'

/** System-assigned (Phase 3C). Never derived from / merged with FinalVerificationStatus. */
export type EvidenceStatus = 'SUPPORTED' | 'CONFLICTING' | 'UNVERIFIED' | 'INSUFFICIENT_EVIDENCE'

/** Admin-assigned (Phase 6). Never derived from / merged with EvidenceStatus. */
export type FinalVerificationStatus = 'VERIFIED' | 'NEEDS_REVIEW' | 'REJECTED'

export type ReportVerificationStatus = 'UNVERIFIED' | 'VERIFIED' | 'REJECTED' | 'SUSPICIOUS'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string
  refresh_token?: string | null
  token_type: string
  user_id: string
  role: UserRole
  expires_in: number
}

export interface AuthUser {
  user_id: string
  email: string
  role: UserRole
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export interface ReportSubmissionRequest {
  text: string
  city: string
  state?: string | null
  latitude?: number | null
  longitude?: number | null
  event_type: EventType | string
  image_url?: string | null
  video_url?: string | null
  location_name?: string | null
}

export interface ReportSubmissionResponse {
  report_id: string
  event_id?: string | null
  evidence_status?: EvidenceStatus | null
  evidence_support_score?: number | null
  verification_status: ReportVerificationStatus
  created_at: string
}

export interface ReportStatusResponse {
  report_id: string
  source_type: string
  text: string
  city: string
  state?: string | null
  event_type: string
  verification_status: ReportVerificationStatus
  evidence_status?: EvidenceStatus | null
  evidence_support_score?: number | null
  created_at: string
  updated_at: string
  event_id?: string | null
  final_verification_status?: FinalVerificationStatus | null
}

export interface ReportListResponse {
  reports: ReportStatusResponse[]
  total: number
  limit: number
  offset: number
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export interface WeatherEvent {
  event_id: string
  event_type: string
  location_name: string
  severity: Severity
  start_time: string
  end_time?: string | null

  // Phase 7 addition: real coordinates extracted from the backend's PostGIS
  // location column (see phase5/api/routes/events.py). Null when a report
  // was submitted without coordinates.
  latitude?: number | null
  longitude?: number | null

  evidence_status: EvidenceStatus
  evidence_support_score?: number | null
  evidence_detail?: Record<string, unknown> | null

  final_verification_status: FinalVerificationStatus

  report_count: number
  unique_sources: number
  member_report_ids: string[]

  reviewed_by?: string | null
  reviewed_at?: string | null
  review_notes?: string | null

  created_at: string
  updated_at: string
}

export interface EventListResponse {
  events: WeatherEvent[]
  total: number
  limit: number
  offset: number
}

export interface EventListFilters {
  status?: FinalVerificationStatus
  evidence_status?: EvidenceStatus
  event_type?: EventType | string
  severity?: Severity
  city?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

// ---------------------------------------------------------------------------
// Admin / Phase 6 verification workflow
// ---------------------------------------------------------------------------

export interface AdminQueueEntry {
  event_id: string
  event_type: string
  location_name: string
  severity: Severity
  start_time: string
  evidence_status: EvidenceStatus
  evidence_support_score?: number | null
  final_verification_status: FinalVerificationStatus
  report_count: number
  created_at: string
  updated_at: string
}

export interface AdminQueueResponse {
  items: AdminQueueEntry[]
  total: number
  limit: number
  offset: number
}

export interface AdminQueueFilters {
  status?: FinalVerificationStatus | 'ALL'
  evidence_status?: EvidenceStatus
  event_type?: EventType | string
  city?: string
  severity?: Severity
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export interface EvidenceReportItem {
  report_id: string
  source_type?: string | null
  source_name?: string | null
  author_id_or_hash?: string | null
  report_timestamp?: string | null
  city?: string | null
  state?: string | null
  text?: string | null
  event_type?: string | null
  verification_status?: ReportVerificationStatus | null
  source_reliability?: number | null
  predicted_event_category?: string | null
  event_classification_confidence?: number | null
  risk_score?: number | null
  risk_label?: string | null
  semantic_similarity_score?: number | null
  is_duplicate: boolean
  is_suspicious: boolean
}

export interface EvidenceEventSummary {
  event_id: string
  event_type: string
  location_name: string
  severity: Severity
  start_time: string
  end_time?: string | null
  evidence_status: EvidenceStatus
  evidence_support_score?: number | null
  final_verification_status: FinalVerificationStatus
  report_count: number
  unique_sources: number
}

export interface EvidenceDetailResponse {
  event: EvidenceEventSummary
  external_evidence?: Record<string, unknown> | null
  reports: EvidenceReportItem[]
}

export interface AdminReviewRequest {
  action: FinalVerificationStatus
  notes?: string | null
}

export interface AdminVerifyResponse {
  success: boolean
  event_id: string
  previous_status: FinalVerificationStatus
  final_verification_status: FinalVerificationStatus
  reviewed_by: string
  reviewed_at: string
  notes?: string | null
}

// ---------------------------------------------------------------------------
// API error shape
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  detail?: string | { msg: string; loc?: (string | number)[] }[]
  code?: string
}
