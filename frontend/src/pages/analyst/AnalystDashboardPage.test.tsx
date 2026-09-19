import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AnalystDashboardPage } from '@/pages/analyst/AnalystDashboardPage'
import * as analyticsHooks from '@/features/analytics/useAnalytics'

function mockAllIntelligenceHooks() {
  vi.spyOn(analyticsHooks, 'useDataQualityAnalytics').mockReturnValue({ data: { total_observations_analyzed: 0, evaluated_observations: 0, insufficient_history_count: 0, missing_value_count: 0, invalid_value_count: 0, zero_variance_count: 0, variables_analyzed: 4, by_source: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useWeatherTrends').mockReturnValue({ data: { trends: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useTemperatureAnalytics').mockReturnValue({ data: { trends: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useRainfallAnalytics').mockReturnValue({ data: { trends: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useSourceComparison').mockReturnValue({ data: { sources: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useAnomalies').mockReturnValue({ data: { total_anomalies: 0, by_variable_severity: [], by_severity: [], by_month: [], by_source: [], by_variable: [], latest: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useEventDistribution').mockReturnValue({ data: { total_events: 0, by_event_type: [], by_severity: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useVerificationAnalytics').mockReturnValue({ data: { total_events: 0, verified: 0, needs_review: 0, rejected: 0 }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useFusionAnalytics').mockReturnValue({ data: { era5_records: 0, openmeteo_records: 0, matched_temporal: 0, matched_temporal_spatial: 0, not_matched: 0, grid_distance_km: null, confidence_count: 0, confidence_mean: null, confidence_min: null, confidence_max: null, agreement_by_variable: [], scientific_note: null }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useCorroborationAnalytics').mockReturnValue({ data: { total_reports: 0, supported: 0, conflicting: 0, unverified: 0, insufficient_evidence: 0, average_evidence_support_score: null, reports_with_a_score: 0, evidence_source_usage: [], honest_note: null }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useIntelligenceAnalytics').mockReturnValue({ data: { total_intelligence_records: 0, matched_sources: 0, source_agreement_mean: null, supported_reports: 0, unverified_reports: 0, conflicting_reports: 0, average_evidence_support_score: null, average_overall_confidence: null, confidence_bands: [], corroboration_counts: [], latest_signals: [], scientific_note: null }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useModelPerformance').mockReturnValue({ data: { horizons: [], temperature: [], rainfall: [], headline: { models_saved: 0 } }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
}

describe('AnalystDashboardPage', () => {
  it('shows a loading state initially', () => {
    mockAllIntelligenceHooks()
    vi.spyOn(analyticsHooks, 'useAnalyticsOverview').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AnalystDashboardPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders real KPI numbers from the database-backed overview endpoint', () => {
    mockAllIntelligenceHooks()
    vi.spyOn(analyticsHooks, 'useAnalyticsOverview').mockReturnValue({
      data: {
        total_weather_observations: 35088,
        total_weather_events: 7,
        total_reports: 10,
        total_anomalies: 1309,
        total_sources: 2,
        verified_events: 3,
        needs_review: 2,
        rejected_events: 2,
        average_temperature: 25.46,
        max_temperature: 44.7,
        total_rainfall: 5855.99,
        measurements_analyzed: 140352,
        anomaly_rate: 0.009327,
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AnalystDashboardPage />)
    expect(screen.getByText('35,088')).toBeInTheDocument()
    expect(screen.getByText('1,309')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument() // verified_events
  })

  it('shows an error state with retry when the overview query fails', () => {
    const refetch = vi.fn()
    mockAllIntelligenceHooks()
    vi.spyOn(analyticsHooks, 'useAnalyticsOverview').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('server unavailable'),
      refetch,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AnalystDashboardPage />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
