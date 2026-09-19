import { useQuery } from '@tanstack/react-query'
import {
  getAnalyticsOverview,
  getDataQualityAnalytics,
  getAnomalyAnalytics,
  getEventDistribution,
  getRainfallAnalytics,
  getSourceComparison,
  getTemperatureAnalytics,
  getVerificationAnalytics,
  getWeatherTrends,
  getFusionAnalytics,
  getCorroborationAnalytics,
  getIntelligenceAnalytics,
  getModelPerformance,
} from '@/services/api/analytics'
import type { AnalyticsFilters, AnomalyFilters, EventDistributionFilters } from '@/types/domain'

/**
 * Analytics hooks are thin TanStack Query wrappers over the
 * database-backed /analytics/* endpoints (backend/api/routes/analytics.py).
 * Every number rendered from these hooks was aggregated in PostgreSQL, not
 * computed here — there is no client-side reduction of raw rows anywhere in
 * this file, unlike the old event-list-based useAnalytics() this replaces.
 *
 * staleTime is set generously (60s) because the underlying data only
 * changes when someone re-runs backend/db/ingest_analytics_data.py or the
 * citizen-report pipeline creates/updates a WeatherEvent — not every few
 * seconds like the admin verification queue.
 */

const STALE_TIME_MS = 60_000

export const analyticsQueryKeys = {
  overview: (filters: AnalyticsFilters = {}) => ['analytics', 'overview', filters] as const,
  dataQuality: ['analytics', 'data-quality'] as const,
  weatherTrends: (filters: AnalyticsFilters) => ['analytics', 'weather-trends', filters] as const,
  rainfall: (filters: AnalyticsFilters) => ['analytics', 'rainfall', filters] as const,
  temperature: (filters: AnalyticsFilters) => ['analytics', 'temperature', filters] as const,
  sourceComparison: (filters: Pick<AnalyticsFilters, 'start_date' | 'end_date'>) =>
    ['analytics', 'source-comparison', filters] as const,
  anomalies: (filters: AnomalyFilters) => ['analytics', 'anomalies', filters] as const,
  eventDistribution: (filters: EventDistributionFilters) => ['analytics', 'event-distribution', filters] as const,
  verification: (filters: Pick<EventDistributionFilters, 'start_date' | 'end_date'>) =>
    ['analytics', 'verification', filters] as const,
}

export function useAnalyticsOverview(filters: AnalyticsFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.overview(filters),
    queryFn: () => getAnalyticsOverview(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useDataQualityAnalytics() {
  return useQuery({
    queryKey: analyticsQueryKeys.dataQuality,
    queryFn: getDataQualityAnalytics,
    staleTime: STALE_TIME_MS * 5,
  })
}

export function useWeatherTrends(filters: AnalyticsFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.weatherTrends(filters),
    queryFn: () => getWeatherTrends(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useRainfallAnalytics(filters: AnalyticsFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.rainfall(filters),
    queryFn: () => getRainfallAnalytics(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useTemperatureAnalytics(filters: AnalyticsFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.temperature(filters),
    queryFn: () => getTemperatureAnalytics(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useSourceComparison(filters: Pick<AnalyticsFilters, 'start_date' | 'end_date'> = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.sourceComparison(filters),
    queryFn: () => getSourceComparison(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useAnomalies(filters: AnomalyFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.anomalies(filters),
    queryFn: () => getAnomalyAnalytics(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useEventDistribution(filters: EventDistributionFilters = {}) {
  return useQuery({
    queryKey: analyticsQueryKeys.eventDistribution(filters),
    queryFn: () => getEventDistribution(filters),
    staleTime: STALE_TIME_MS,
  })
}

export function useVerificationAnalytics(
  filters: Pick<EventDistributionFilters, 'start_date' | 'end_date'> = {}
) {
  return useQuery({
    queryKey: analyticsQueryKeys.verification(filters),
    queryFn: () => getVerificationAnalytics(filters),
    staleTime: STALE_TIME_MS,
  })
}


export function useFusionAnalytics() {
  return useQuery({
    queryKey: ['analytics', 'fusion'],
    queryFn: getFusionAnalytics,
    staleTime: STALE_TIME_MS * 5,
  })
}

export function useCorroborationAnalytics() {
  return useQuery({
    queryKey: ['analytics', 'corroboration'],
    queryFn: getCorroborationAnalytics,
    staleTime: STALE_TIME_MS * 5,
  })
}

export function useIntelligenceAnalytics() {
  return useQuery({
    queryKey: ['analytics', 'intelligence'],
    queryFn: getIntelligenceAnalytics,
    staleTime: STALE_TIME_MS * 5,
  })
}

export function useModelPerformance() {
  return useQuery({
    queryKey: ['analytics', 'model-performance'],
    queryFn: getModelPerformance,
    staleTime: STALE_TIME_MS * 5,
  })
}
