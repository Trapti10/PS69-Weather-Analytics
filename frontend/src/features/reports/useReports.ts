import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/services/api/client'
import { submitReport } from '@/services/api/reports'
import type { ReportListResponse, ReportSubmissionRequest } from '@/types/domain'
import { MY_REPORTS_POLL_INTERVAL_MS } from '@/constants/status'

export const reportsQueryKeys = {
  mine: (limit: number, offset: number) => ['reports', 'me', { limit, offset }] as const,
}

export function useSubmitReportMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReportSubmissionRequest) => submitReport(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', 'me'] })
    },
  })
}

export interface UseMyReportsOptions {
  limit?: number
  offset?: number
  /** Poll while the citizen is actively watching a freshly submitted report resolve. */
  poll?: boolean
}

export function useMyReports({ limit = 20, offset = 0, poll = false }: UseMyReportsOptions = {}) {
  return useQuery({
    queryKey: reportsQueryKeys.mine(limit, offset),
    queryFn: async () => {
      const { data } = await apiClient.get<ReportListResponse>('/reports/me', {
        params: { limit, offset },
      })
      return data
    },
    refetchInterval: poll ? MY_REPORTS_POLL_INTERVAL_MS : false,
    staleTime: poll ? 0 : 15_000,
  })
}
