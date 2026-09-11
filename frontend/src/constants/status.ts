import type { EvidenceStatus, FinalVerificationStatus, Severity } from '@/types/domain'

/**
 * Evidence Status and Final Verification Status are two SEPARATE axes and
 * must never be merged or displayed as if one implies the other.
 * (e.g. CONFLICTING evidence must never render as "FAKE" or "REJECTED".)
 */

export const EVIDENCE_STATUS_LABEL: Record<EvidenceStatus, string> = {
  SUPPORTED: 'Supported',
  CONFLICTING: 'Conflicting',
  UNVERIFIED: 'Unverified',
  INSUFFICIENT_EVIDENCE: 'Insufficient Evidence',
}

export const EVIDENCE_STATUS_TONE: Record<EvidenceStatus, 'success' | 'warning' | 'muted' | 'info'> = {
  SUPPORTED: 'success',
  CONFLICTING: 'warning',
  UNVERIFIED: 'muted',
  INSUFFICIENT_EVIDENCE: 'info',
}

export const FINAL_STATUS_LABEL: Record<FinalVerificationStatus, string> = {
  VERIFIED: 'Verified',
  NEEDS_REVIEW: 'Needs Review',
  REJECTED: 'Rejected',
}

export const FINAL_STATUS_TONE: Record<FinalVerificationStatus, 'success' | 'warning' | 'danger'> = {
  VERIFIED: 'success',
  NEEDS_REVIEW: 'warning',
  REJECTED: 'danger',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  EXTREME: 'Extreme',
}

export const SEVERITY_TONE: Record<Severity, 'muted' | 'info' | 'warning' | 'danger'> = {
  LOW: 'muted',
  MEDIUM: 'info',
  HIGH: 'warning',
  EXTREME: 'danger',
}

export const EVENT_TYPE_LABEL: Record<string, string> = {
  RAINFALL: 'Rainfall',
  THUNDERSTORM: 'Thunderstorm',
  FLOODING: 'Flooding',
  HEATWAVE: 'Heatwave',
  FOG: 'Fog',
  DUST_STORM: 'Dust Storm',
  STRONG_WIND: 'Strong Wind',
  OTHER: 'Other',
}

export const ADMIN_QUEUE_POLL_INTERVAL_MS = 4000
export const MY_REPORTS_POLL_INTERVAL_MS = 5000
