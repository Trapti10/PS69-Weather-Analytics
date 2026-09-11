import { apiClient } from '@/services/api/client'
import type { ReportStatusResponse, ReportSubmissionRequest, ReportSubmissionResponse } from '@/types/domain'

export async function submitReport(payload: ReportSubmissionRequest): Promise<ReportSubmissionResponse> {
  const { data } = await apiClient.post<ReportSubmissionResponse>('/reports', payload)
  return data
}

export async function getReportStatus(reportId: string): Promise<ReportStatusResponse> {
  const { data } = await apiClient.get<ReportStatusResponse>(`/reports/${reportId}/status`)
  return data
}
