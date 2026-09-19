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

// ---------------------------------------------------------------------------
// Analytics (database-backed weather intelligence — mirrors
// backend/api/schemas.py "ANALYTICS SCHEMAS" exactly). Backed by
// weather_observations / weather_anomalies (real ERA5 + Open-Meteo +
// Phase 4C data) plus the existing WeatherEvent table. ANALYST/ADMIN only.
// ---------------------------------------------------------------------------

/** Phase 4C's own severity vocabulary — distinct from Severity (event
 * severity is LOW/MEDIUM/HIGH/EXTREME). Never conflate the two. */
export type AnomalySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface AnalyticsFilters {
  source?: string
  start_date?: string
  end_date?: string
}

export interface AnalyticsOverview {
  total_weather_observations: number
  total_weather_events: number
  total_reports: number
  total_anomalies: number
  total_sources: number
  verified_events: number
  needs_review: number
  rejected_events: number
  average_temperature?: number | null
  max_temperature?: number | null
  total_rainfall?: number | null
  measurements_analyzed?: number | null
  anomaly_rate?: number | null
  observations_date_range_start?: string | null
  observations_date_range_end?: string | null
}

export interface DataQualitySourceSummary {
  source: string
  input_records: number
  records_without_timestamp: number
  duplicate_timestamps_dropped: number
  invalid_rainfall_count: number
}

export interface DataQualityAnalytics {
  total_observations_analyzed: number
  evaluated_observations: number
  insufficient_history_count: number
  missing_value_count: number
  invalid_value_count: number
  zero_variance_count: number
  variables_analyzed: number
  by_source: DataQualitySourceSummary[]
}

export interface WeatherTrendPoint {
  date: string
  average_temperature?: number | null
  rainfall?: number | null
  average_humidity?: number | null
  average_wind_speed?: number | null
  average_pressure?: number | null
  observation_count: number
}

export interface WeatherTrendsResponse {
  trends: WeatherTrendPoint[]
  source?: string | null
  start_date?: string | null
  end_date?: string | null
}

export interface RainfallTrendPoint {
  date: string
  total_rainfall?: number | null
  observation_count: number
}

export interface RainfallAnalytics {
  trends: RainfallTrendPoint[]
  total_rainfall?: number | null
  max_daily_rainfall?: number | null
}

export interface TemperatureTrendPoint {
  date: string
  average_temperature?: number | null
  min_temperature?: number | null
  max_temperature?: number | null
  observation_count: number
}

export interface TemperatureAnalytics {
  trends: TemperatureTrendPoint[]
  average_temperature?: number | null
  min_temperature?: number | null
  max_temperature?: number | null
}

export interface SourceComparisonItem {
  source: string
  observation_count: number
  average_temperature?: number | null
  rainfall?: number | null
  average_humidity?: number | null
  average_wind_speed?: number | null
}

export interface SourceComparisonResponse {
  sources: SourceComparisonItem[]
}

export interface AnomalyFilters extends AnalyticsFilters {
  variable?: string
  severity?: AnomalySeverity
  latest_limit?: number
}

export interface AnomalyVariableSeverityCount {
  variable: string
  severity: AnomalySeverity
  count: number
}

export interface AnomalySeverityCount {
  severity: AnomalySeverity
  count: number
}

export interface AnomalyItem {
  id: string
  source: string
  observed_at: string
  variable: string
  observed_value?: number | null
  baseline_value?: number | null
  severity: AnomalySeverity
  explanation?: string | null
  latitude?: number | null
  longitude?: number | null
  location_name?: string | null
}

export interface AnomalyAnalytics {
  total_anomalies: number
  by_variable_severity: AnomalyVariableSeverityCount[]
  by_severity: AnomalySeverityCount[]
  by_month: Array<{ month: string; count: number }>
  by_source: Array<{ source: string; count: number }>
  by_variable: Array<{ variable: string; count: number }>
  latest: AnomalyItem[]
}

export interface EventDistributionFilters {
  start_date?: string
  end_date?: string
  city?: string
}

export interface EventTypeCount {
  event_type: string
  count: number
}

export interface EventSeverityCount {
  severity: Severity
  count: number
}

export interface EventDistribution {
  total_events: number
  by_event_type: EventTypeCount[]
  by_severity: EventSeverityCount[]
}

export interface VerificationAnalytics {
  total_events: number
  verified: number
  needs_review: number
  rejected: number
}


// ---------------------------------------------------------------------------
// Extended scientific/weather intelligence
// ---------------------------------------------------------------------------

export interface FusionAnalytics {
  era5_records: number
  openmeteo_records: number
  matched_temporal: number
  matched_temporal_spatial: number
  not_matched: number
  grid_distance_km?: number | null
  confidence_count: number
  confidence_mean?: number | null
  confidence_min?: number | null
  confidence_max?: number | null
  agreement_by_variable: Array<{
    variable: string
    SOURCE_AGREEMENT_HIGH?: number
    SOURCE_AGREEMENT_MEDIUM?: number
    SOURCE_DISAGREEMENT?: number
  }>
  scientific_note?: string | null
}

export interface CorroborationAnalytics {
  total_reports: number
  supported: number
  conflicting: number
  unverified: number
  insufficient_evidence: number
  average_evidence_support_score?: number | null
  reports_with_a_score: number
  evidence_source_usage: Array<{ source: string; count: number }>
  honest_note?: string | null
}

export interface IntelligenceAnalytics {
  total_intelligence_records: number
  matched_sources: number
  source_agreement_mean?: number | null
  supported_reports: number
  unverified_reports: number
  conflicting_reports: number
  average_evidence_support_score?: number | null
  average_overall_confidence?: number | null
  confidence_bands: Array<{ band: string; count: number }>
  corroboration_counts: Array<{ status: string; count: number }>
  latest_signals: Array<{
    timestamp?: string | null
    latitude?: number | null
    longitude?: number | null
    sources: string[]
    source_agreement?: string | null
    confidence?: number | null
    corroboration?: string | null
    event_category?: string | null
  }>
  scientific_note?: string | null
}

export interface ModelPerformanceRow {
  model: string
  target: string
  horizon_h: number
  mae?: number | null
  rmse?: number | null
  r2?: number | null
  precision?: number | null
  recall?: number | null
  f1?: number | null
  roc_auc?: number | null
  train_samples?: number | null
  test_samples?: number | null
}

export interface ModelPerformance {
  horizons: number[]
  temperature: ModelPerformanceRow[]
  rainfall: ModelPerformanceRow[]
  headline: Record<string, number | string | null>
}

export interface ResearchArtifact {
  artifact_id: string
  name: string
  category: string
  format: string
  size_bytes: number
  row_count?: number | null
  description: string
  source_path: string
  download_endpoint: string
}

export interface ResearchArtifactListResponse {
  artifacts: ResearchArtifact[]
}

export interface ResearchArtifactPreviewResponse {
  artifact: ResearchArtifact
  columns: string[]
  rows: Array<Record<string, unknown>>
}

export interface LocationSearchItem {
  name: string
  latitude?: number | null
  longitude?: number | null
  observation_count: number
  anomaly_count: number
  event_count: number
  coverage_start?: string | null
  coverage_end?: string | null
}

export interface LocationSearchResponse {
  locations: LocationSearchItem[]
}

export interface PublicLocationEvent {
  event_id: string
  event_type: string
  location_name: string
  severity: Severity
  start_time: string
  end_time?: string | null
  final_verification_status: FinalVerificationStatus
}

export interface PublicLocationSummary {
  location: string
  latitude?: number | null
  longitude?: number | null
  dataset_coverage_start?: string | null
  dataset_coverage_end?: string | null
  observation_count: number
  anomaly_count: number
  events: PublicLocationEvent[]
  note?: string | null
}
