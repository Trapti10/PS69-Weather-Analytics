import { apiClient } from '@/services/api/client'
import type {
  AdminQueueFilters,
  AdminQueueResponse,
  AdminReviewRequest,
  AdminVerifyResponse,
  EvidenceDetailResponse,
} from '@/types/domain'

export async function getVerificationQueue(filters: AdminQueueFilters = {}): Promise<AdminQueueResponse> {
  const { data } = await apiClient.get<AdminQueueResponse>('/admin/verification-queue', {
    params: {
      status: filters.status ?? 'NEEDS_REVIEW',
      evidence_status: filters.evidence_status || undefined,
      event_type: filters.event_type || undefined,
      city: filters.city || undefined,
      severity: filters.severity || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
      limit: filters.limit ?? 20,
      offset: filters.offset ?? 0,
    },
  })
  return data
}

export async function getEventEvidence(eventId: string): Promise<EvidenceDetailResponse> {
  const { data } = await apiClient.get<EvidenceDetailResponse>(`/admin/events/${eventId}/evidence`)
  return data
}

export async function verifyEvent(eventId: string, payload: AdminReviewRequest): Promise<AdminVerifyResponse> {
  const { data } = await apiClient.post<AdminVerifyResponse>(`/admin/events/${eventId}/verify`, payload)
  return data
}
