import { apiClient } from '@/services/api/client'
import type { ResearchArtifactListResponse, ResearchArtifactPreviewResponse } from '@/types/domain'

export async function getResearchArtifacts(): Promise<ResearchArtifactListResponse> {
  const { data } = await apiClient.get<ResearchArtifactListResponse>('/research/artifacts')
  return data
}

export async function previewResearchArtifact(id: string, limit = 30): Promise<ResearchArtifactPreviewResponse> {
  const { data } = await apiClient.get<ResearchArtifactPreviewResponse>(`/research/artifacts/${id}/preview`, {
    params: { limit },
  })
  return data
}

export async function downloadResearchArtifact(id: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/research/artifacts/${id}/download`, {
    responseType: 'blob',
  })
  return data
}
