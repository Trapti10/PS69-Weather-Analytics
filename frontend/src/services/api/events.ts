import { apiClient } from '@/services/api/client'
import type { EventListFilters, EventListResponse, WeatherEvent } from '@/types/domain'

export async function listEvents(filters: EventListFilters = {}): Promise<EventListResponse> {
  const { data } = await apiClient.get<EventListResponse>('/events', {
    params: {
      status: filters.status,
      evidence_status: filters.evidence_status,
      event_type: filters.event_type,
      severity: filters.severity,
      city: filters.city || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    },
  })
  return data
}

export async function getEvent(eventId: string): Promise<WeatherEvent> {
  const { data } = await apiClient.get<WeatherEvent>(`/events/${eventId}`)
  return data
}
