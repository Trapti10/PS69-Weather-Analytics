import { useQuery } from '@tanstack/react-query'
import { getLocationSummary, searchLocations } from '@/services/api/locations'

export function useLocationSearch(q: string, enabled = true) {
  return useQuery({
    queryKey: ['locations', 'search', q],
    queryFn: () => searchLocations(q),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLocationSummary(location: string | null) {
  return useQuery({
    queryKey: ['locations', 'summary', location],
    queryFn: () => getLocationSummary(location!),
    enabled: Boolean(location),
    staleTime: 60 * 1000,
  })
}
