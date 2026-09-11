import { Badge } from '@/components/ui/Badge'
import type { EvidenceStatus, FinalVerificationStatus, Severity } from '@/types/domain'
import {
  EVIDENCE_STATUS_LABEL,
  EVIDENCE_STATUS_TONE,
  FINAL_STATUS_LABEL,
  FINAL_STATUS_TONE,
  SEVERITY_LABEL,
  SEVERITY_TONE,
} from '@/constants/status'

/**
 * IMPORTANT: Evidence Status and Final Verification Status are two separate,
 * system- vs admin-owned axes. This component renders each with its own
 * label/tone mapping and never infers one from the other (e.g. CONFLICTING
 * evidence is never shown as "fake" or "rejected").
 */

export function EvidenceStatusBadge({ status }: { status: EvidenceStatus }) {
  return <Badge tone={EVIDENCE_STATUS_TONE[status]}>{EVIDENCE_STATUS_LABEL[status]}</Badge>
}

export function FinalStatusBadge({ status }: { status: FinalVerificationStatus }) {
  return <Badge tone={FINAL_STATUS_TONE[status]}>{FINAL_STATUS_LABEL[status]}</Badge>
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge tone={SEVERITY_TONE[severity]}>{SEVERITY_LABEL[severity]}</Badge>
}
