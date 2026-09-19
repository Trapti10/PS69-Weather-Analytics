import { apiClient } from '@/services/api/client'
import type {
  AnalyticsFilters,
  DataQualityAnalytics,
  AnalyticsOverview,
  AnomalyAnalytics,
  AnomalyFilters,
  EventDistribution,
  EventDistributionFilters,
  RainfallAnalytics,
  SourceComparisonResponse,
  TemperatureAnalytics,
  VerificationAnalytics,
  WeatherTrendsResponse,
  FusionAnalytics,
  CorroborationAnalytics,
  IntelligenceAnalytics,
  ModelPerformance,
} from '@/types/domain'

export async function getAnalyticsOverview(filters: AnalyticsFilters = {}): Promise<AnalyticsOverview> {
  const { data } = await apiClient.get<AnalyticsOverview>('/analytics/overview', { params: filters })
  return data
}

export async function getDataQualityAnalytics(): Promise<DataQualityAnalytics> {
  const { data } = await apiClient.get<DataQualityAnalytics>('/analytics/data-quality')
  return data
}

export async function getWeatherTrends(filters: AnalyticsFilters = {}): Promise<WeatherTrendsResponse> {
  const { data } = await apiClient.get<WeatherTrendsResponse>('/analytics/weather-trends', { params: filters })
  return data
}

export async function getRainfallAnalytics(filters: AnalyticsFilters = {}): Promise<RainfallAnalytics> {
  const { data } = await apiClient.get<RainfallAnalytics>('/analytics/rainfall', { params: filters })
  return data
}

export async function getTemperatureAnalytics(filters: AnalyticsFilters = {}): Promise<TemperatureAnalytics> {
  const { data } = await apiClient.get<TemperatureAnalytics>('/analytics/temperature', { params: filters })
  return data
}

export async function getSourceComparison(
  filters: Pick<AnalyticsFilters, 'start_date' | 'end_date'> = {}
): Promise<SourceComparisonResponse> {
  const { data } = await apiClient.get<SourceComparisonResponse>('/analytics/source-comparison', {
    params: filters,
  })
  return data
}

export async function getAnomalyAnalytics(filters: AnomalyFilters = {}): Promise<AnomalyAnalytics> {
  const { data } = await apiClient.get<AnomalyAnalytics>('/analytics/anomalies', { params: filters })
  return data
}

export async function getEventDistribution(filters: EventDistributionFilters = {}): Promise<EventDistribution> {
  const { data } = await apiClient.get<EventDistribution>('/analytics/event-distribution', { params: filters })
  return data
}

export async function getVerificationAnalytics(
  filters: Pick<EventDistributionFilters, 'start_date' | 'end_date'> = {}
): Promise<VerificationAnalytics> {
  const { data } = await apiClient.get<VerificationAnalytics>('/analytics/verification', { params: filters })
  return data
}


export async function getFusionAnalytics(): Promise<FusionAnalytics> {
  const { data } = await apiClient.get<FusionAnalytics>('/analytics/fusion')
  return data
}

export async function getCorroborationAnalytics(): Promise<CorroborationAnalytics> {
  const { data } = await apiClient.get<CorroborationAnalytics>('/analytics/corroboration')
  return data
}

export async function getIntelligenceAnalytics(): Promise<IntelligenceAnalytics> {
  const { data } = await apiClient.get<IntelligenceAnalytics>('/analytics/intelligence')
  return data
}

export async function getModelPerformance(): Promise<ModelPerformance> {
  const { data } = await apiClient.get<ModelPerformance>('/analytics/model-performance')
  return data
}
