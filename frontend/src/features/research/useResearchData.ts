import { useMutation, useQuery } from '@tanstack/react-query'
import { downloadResearchArtifact, getResearchArtifacts, previewResearchArtifact } from '@/services/api/research'

export function useResearchArtifacts() {
  return useQuery({
    queryKey: ['research', 'artifacts'],
    queryFn: getResearchArtifacts,
    staleTime: 5 * 60 * 1000,
  })
}

export function useResearchArtifactPreview(id: string | null) {
  return useQuery({
    queryKey: ['research', 'preview', id],
    queryFn: () => previewResearchArtifact(id!),
    enabled: Boolean(id),
    staleTime: 5 * 60 * 1000,
  })
}

export function useResearchArtifactDownload() {
  return useMutation({
    mutationFn: downloadResearchArtifact,
  })
}
