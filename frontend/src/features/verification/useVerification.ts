import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getEventEvidence, getVerificationQueue, verifyEvent } from '@/services/api/admin'
import type { AdminQueueFilters, AdminReviewRequest } from '@/types/domain'
import { ADMIN_QUEUE_POLL_INTERVAL_MS } from '@/constants/status'

export const verificationQueryKeys = {
  queue: (filters: AdminQueueFilters) => ['admin', 'queue', filters] as const,
  evidence: (eventId: string) => ['admin', 'evidence', eventId] as const,
}

export interface UseVerificationQueueOptions {
  filters?: AdminQueueFilters
  /** Disable near-real-time polling, e.g. when the tab is not focused. */
  poll?: boolean
}

export function useVerificationQueue({ filters = {}, poll = true }: UseVerificationQueueOptions = {}) {
  return useQuery({
    queryKey: verificationQueryKeys.queue(filters),
    queryFn: () => getVerificationQueue(filters),
    refetchInterval: poll ? ADMIN_QUEUE_POLL_INTERVAL_MS : false,
    refetchIntervalInBackground: false,
    staleTime: 0,
  })
}

export function useEventEvidence(eventId: string | undefined) {
  return useQuery({
    queryKey: verificationQueryKeys.evidence(eventId ?? ''),
    queryFn: () => getEventEvidence(eventId as string),
    enabled: !!eventId,
  })
}

export function useVerifyEventMutation(eventId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AdminReviewRequest) => verifyEvent(eventId as string, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'queue'] })
      if (eventId) {
        queryClient.invalidateQueries({ queryKey: verificationQueryKeys.evidence(eventId) })
      }
      queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}
