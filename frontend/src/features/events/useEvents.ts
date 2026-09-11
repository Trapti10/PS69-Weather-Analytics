import { useQuery } from '@tanstack/react-query'
import { getEvent, listEvents } from '@/services/api/events'
import type { EventListFilters } from '@/types/domain'

export const eventsQueryKeys = {
  list: (filters: EventListFilters) => ['events', 'list', filters] as const,
  detail: (id: string) => ['events', 'detail', id] as const,
}

export function useEvents(filters: EventListFilters = {}) {
  return useQuery({
    queryKey: eventsQueryKeys.list(filters),
    queryFn: () => listEvents(filters),
    staleTime: 15_000,
  })
}

export function useEvent(eventId: string | undefined) {
  return useQuery({
    queryKey: eventsQueryKeys.detail(eventId ?? ''),
    queryFn: () => getEvent(eventId as string),
    enabled: !!eventId,
  })
}
