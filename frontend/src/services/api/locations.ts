import { apiClient } from '@/services/api/client'
import type { LocationSearchResponse, PublicLocationSummary } from '@/types/domain'

export async function searchLocations(q: string): Promise<LocationSearchResponse> {
  const { data } = await apiClient.get<LocationSearchResponse>('/locations/search', { params: { q } })
  return data
}

export async function getLocationSummary(location: string): Promise<PublicLocationSummary> {
  const { data } = await apiClient.get<PublicLocationSummary>(`/locations/${encodeURIComponent(location)}/summary`)
  return data
}
