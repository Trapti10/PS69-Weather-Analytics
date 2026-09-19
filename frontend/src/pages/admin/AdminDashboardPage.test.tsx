import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage'
import * as verificationModule from '@/features/verification/useVerification'
import * as analyticsHooks from '@/features/analytics/useAnalytics'

function queueResult(total: number) {
  return {
    data: { items: [], total, limit: 1, offset: 0 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any
}

function emptyAnalyticsResult<T>(data: T) {
  return {
    data,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any
}

function mockIntelligenceHooksAsEmpty() {
  vi.spyOn(analyticsHooks, 'useAnalyticsOverview').mockReturnValue(
    emptyAnalyticsResult({
      total_weather_observations: 0,
      total_weather_events: 0,
      total_reports: 0,
      total_anomalies: 0,
      total_sources: 0,
      verified_events: 0,
      needs_review: 0,
      rejected_events: 0,
      average_temperature: null,
      max_temperature: null,
      total_rainfall: null,
      measurements_analyzed: 0,
      anomaly_rate: 0,
    })
  )
  vi.spyOn(analyticsHooks, 'useDataQualityAnalytics').mockReturnValue({ data: { total_observations_analyzed: 0, evaluated_observations: 0, insufficient_history_count: 0, missing_value_count: 0, invalid_value_count: 0, zero_variance_count: 0, variables_analyzed: 4, by_source: [] }, isLoading: false, isError: false, error: null, refetch: vi.fn() } as any)
  vi.spyOn(analyticsHooks, 'useWeatherTrends').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useTemperatureAnalytics').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useRainfallAnalytics').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useSourceComparison').mockReturnValue(emptyAnalyticsResult({ sources: [] }))
  vi.spyOn(analyticsHooks, 'useAnomalies').mockReturnValue(
    emptyAnalyticsResult({ total_anomalies: 0, by_variable_severity: [], by_severity: [], by_month: [], by_source: [], by_variable: [], latest: [] })
  )
  vi.spyOn(analyticsHooks, 'useEventDistribution').mockReturnValue(
    emptyAnalyticsResult({ total_events: 0, by_event_type: [], by_severity: [] })
  )
  vi.spyOn(analyticsHooks, 'useVerificationAnalytics').mockReturnValue(
    emptyAnalyticsResult({ total_events: 0, verified: 0, needs_review: 0, rejected: 0 })
  )
  vi.spyOn(analyticsHooks, 'useFusionAnalytics').mockReturnValue(emptyAnalyticsResult({
    era5_records: 0, openmeteo_records: 0, matched_temporal: 0, matched_temporal_spatial: 0, not_matched: 0,
    grid_distance_km: null, confidence_count: 0, confidence_mean: null, confidence_min: null, confidence_max: null, agreement_by_variable: [], scientific_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useCorroborationAnalytics').mockReturnValue(emptyAnalyticsResult({
    total_reports: 0, supported: 0, conflicting: 0, unverified: 0, insufficient_evidence: 0, average_evidence_support_score: null, reports_with_a_score: 0, evidence_source_usage: [], honest_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useIntelligenceAnalytics').mockReturnValue(emptyAnalyticsResult({
    total_intelligence_records: 0, matched_sources: 0, source_agreement_mean: null, supported_reports: 0, unverified_reports: 0, conflicting_reports: 0, average_evidence_support_score: null, average_overall_confidence: null, confidence_bands: [], corroboration_counts: [], latest_signals: [], scientific_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useModelPerformance').mockReturnValue(emptyAnalyticsResult({ horizons: [], temperature: [], rainfall: [], headline: { models_saved: 0 } }))
}

describe('AdminDashboardPage', () => {
  it('shows both the operational verification counts and the weather intelligence section', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue')
      .mockReturnValueOnce(queueResult(4)) // needs review
      .mockReturnValueOnce(queueResult(9)) // verified
      .mockReturnValueOnce(queueResult(1)) // rejected
    mockIntelligenceHooksAsEmpty()

    renderWithProviders(<AdminDashboardPage />)

    // Operational verification counts remain part of the admin workspace.
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open verification queue/i })).toBeInTheDocument()

    // Weather intelligence section is present (shared with Analyst)
    expect(screen.getByText(/no weather intelligence data loaded yet/i)).toBeInTheDocument()
  })

  it('never renders verify/reject controls inside the intelligence section itself', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue')
      .mockReturnValueOnce(queueResult(0))
      .mockReturnValueOnce(queueResult(0))
      .mockReturnValueOnce(queueResult(0))
    mockIntelligenceHooksAsEmpty()

    renderWithProviders(<AdminDashboardPage />)

    // The only actionable control on this page is "Open verification queue" —
    // the intelligence section itself must stay read-only, same as Analyst's.
    expect(screen.queryByRole('button', { name: /^verify$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^reject$/i })).not.toBeInTheDocument()
  })
})
