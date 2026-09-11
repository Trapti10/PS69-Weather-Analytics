import { useQuery } from '@tanstack/react-query'
import { listEvents } from '@/services/api/events'
import type { WeatherEvent } from '@/types/domain'
import { EVENT_TYPE_LABEL } from '@/constants/status'

/**
 * The backend has no dedicated analytics/aggregation endpoint. Rather than
 * hardcode chart numbers, this hook pulls the real event list (analysts/admins
 * see every event, per GET /events role-based visibility) and derives all
 * metrics client-side from that live data. Capped at 500 (the API's max page
 * size) — acceptable for the current MVP data volumes; a true aggregation
 * endpoint would be the next backend improvement if event volume grows.
 */

export interface AnalyticsSummary {
  totalEvents: number
  verifiedCount: number
  needsReviewCount: number
  rejectedCount: number
  byCategory: { category: string; label: string; count: number }[]
  byDate: { date: string; count: number }[]
  byLocation: { location: string; count: number }[]
}

function toDateKey(iso: string): string {
  return iso.slice(0, 10)
}

function summarize(events: WeatherEvent[]): AnalyticsSummary {
  const byCategoryMap = new Map<string, number>()
  const byDateMap = new Map<string, number>()
  const byLocationMap = new Map<string, number>()

  let verifiedCount = 0
  let needsReviewCount = 0
  let rejectedCount = 0

  for (const e of events) {
    byCategoryMap.set(e.event_type, (byCategoryMap.get(e.event_type) ?? 0) + 1)
    byLocationMap.set(e.location_name, (byLocationMap.get(e.location_name) ?? 0) + 1)
    const dateKey = toDateKey(e.start_time)
    byDateMap.set(dateKey, (byDateMap.get(dateKey) ?? 0) + 1)

    if (e.final_verification_status === 'VERIFIED') verifiedCount += 1
    else if (e.final_verification_status === 'NEEDS_REVIEW') needsReviewCount += 1
    else if (e.final_verification_status === 'REJECTED') rejectedCount += 1
  }

  const byCategory = Array.from(byCategoryMap.entries())
    .map(([category, count]) => ({ category, label: EVENT_TYPE_LABEL[category] ?? category, count }))
    .sort((a, b) => b.count - a.count)

  const byDate = Array.from(byDateMap.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date))

  const byLocation = Array.from(byLocationMap.entries())
    .map(([location, count]) => ({ location, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  return {
    totalEvents: events.length,
    verifiedCount,
    needsReviewCount,
    rejectedCount,
    byCategory,
    byDate,
    byLocation,
  }
}

export function useAnalytics() {
  const query = useQuery({
    queryKey: ['analytics', 'events-summary'],
    queryFn: () => listEvents({ limit: 500, offset: 0 }),
    staleTime: 30_000,
  })

  return {
    ...query,
    summary: query.data ? summarize(query.data.events) : undefined,
  }
}
