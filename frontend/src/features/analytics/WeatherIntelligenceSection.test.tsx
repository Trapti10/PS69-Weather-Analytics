import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { WeatherIntelligenceSection } from '@/features/analytics/WeatherIntelligenceSection'
import * as analyticsHooks from '@/features/analytics/useAnalytics'

function baseQueryResult<T>(data: T | undefined, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    data,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any
}

const EMPTY_OVERVIEW = {
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
}

const POPULATED_OVERVIEW = {
  total_weather_observations: 35088,
  total_weather_events: 12,
  total_reports: 20,
  total_anomalies: 1309,
  total_sources: 2,
  verified_events: 5,
  needs_review: 4,
  rejected_events: 3,
  average_temperature: 25.46,
  max_temperature: 44.7,
  total_rainfall: 5855.99,
  measurements_analyzed: 140352,
  anomaly_rate: 0.009327,
}

function mockAllHooks({
  overview = baseQueryResult(EMPTY_OVERVIEW),
  trends = baseQueryResult({ trends: [] }),
  temperature = baseQueryResult({ trends: [] }),
  rainfall = baseQueryResult({ trends: [] }),
  sourceComparison = baseQueryResult({ sources: [] }),
  anomalies = baseQueryResult({ total_anomalies: 0, by_variable_severity: [], by_severity: [], by_month: [], by_source: [], by_variable: [], latest: [] }),
  eventDistribution = baseQueryResult({ total_events: 0, by_event_type: [], by_severity: [] }),
  verification = baseQueryResult({ total_events: 0, verified: 0, needs_review: 0, rejected: 0 }),
} = {}) {
  vi.spyOn(analyticsHooks, 'useAnalyticsOverview').mockReturnValue(overview)
  vi.spyOn(analyticsHooks, 'useDataQualityAnalytics').mockReturnValue(baseQueryResult({
    total_observations_analyzed: 0, evaluated_observations: 0, insufficient_history_count: 0, missing_value_count: 0,
    invalid_value_count: 0, zero_variance_count: 0, variables_analyzed: 4, by_source: [],
  }))
  vi.spyOn(analyticsHooks, 'useWeatherTrends').mockReturnValue(trends)
  vi.spyOn(analyticsHooks, 'useTemperatureAnalytics').mockReturnValue(temperature)
  vi.spyOn(analyticsHooks, 'useRainfallAnalytics').mockReturnValue(rainfall)
  vi.spyOn(analyticsHooks, 'useSourceComparison').mockReturnValue(sourceComparison)
  vi.spyOn(analyticsHooks, 'useAnomalies').mockReturnValue(anomalies)
  vi.spyOn(analyticsHooks, 'useEventDistribution').mockReturnValue(eventDistribution)
  vi.spyOn(analyticsHooks, 'useVerificationAnalytics').mockReturnValue(verification)
  vi.spyOn(analyticsHooks, 'useFusionAnalytics').mockReturnValue(baseQueryResult({
    era5_records: 0, openmeteo_records: 0, matched_temporal: 0, matched_temporal_spatial: 0, not_matched: 0,
    grid_distance_km: null, confidence_count: 0, confidence_mean: null, confidence_min: null, confidence_max: null,
    agreement_by_variable: [], scientific_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useCorroborationAnalytics').mockReturnValue(baseQueryResult({
    total_reports: 0, supported: 0, conflicting: 0, unverified: 0, insufficient_evidence: 0,
    average_evidence_support_score: null, reports_with_a_score: 0, evidence_source_usage: [], honest_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useIntelligenceAnalytics').mockReturnValue(baseQueryResult({
    total_intelligence_records: 0, matched_sources: 0, source_agreement_mean: null, supported_reports: 0,
    unverified_reports: 0, conflicting_reports: 0, average_evidence_support_score: null, average_overall_confidence: null,
    confidence_bands: [], corroboration_counts: [], latest_signals: [], scientific_note: null,
  }))
  vi.spyOn(analyticsHooks, 'useModelPerformance').mockReturnValue(baseQueryResult({
    horizons: [], temperature: [], rainfall: [], headline: { models_saved: 0 },
  }))
}

describe('WeatherIntelligenceSection', () => {
  it('shows a loading state while the overview KPI query is pending', () => {
    mockAllHooks({ overview: baseQueryResult(undefined, { isLoading: true }) })
    renderWithProviders(<WeatherIntelligenceSection />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows an error state with retry when the overview query fails', () => {
    mockAllHooks({
      overview: baseQueryResult(undefined, { isError: true, error: new Error('network down') }),
    })
    renderWithProviders(<WeatherIntelligenceSection />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows an empty-data message when nothing has been ingested yet', () => {
    mockAllHooks()
    renderWithProviders(<WeatherIntelligenceSection />)
    expect(screen.getByText(/no weather intelligence data loaded yet/i)).toBeInTheDocument()
    expect(screen.getByText(/ingest_analytics_data/)).toBeInTheDocument()
  })

  it('renders real aggregated KPI numbers from the overview endpoint, not hardcoded figures', () => {
    mockAllHooks({ overview: baseQueryResult(POPULATED_OVERVIEW) })
    renderWithProviders(<WeatherIntelligenceSection />)

    expect(screen.getByText('35,088')).toBeInTheDocument() // total_weather_observations
    expect(screen.getByText('140,352')).toBeInTheDocument() // measurements_analyzed
    expect(screen.getByText('0.93%')).toBeInTheDocument() // anomaly_rate
    expect(screen.getByText('1,309')).toBeInTheDocument() // total_anomalies
    expect(screen.getByText('25.5°C')).toBeInTheDocument() // average_temperature
    expect(screen.getByText(/5,855\.99\s*mm/)).toBeInTheDocument() // total_rainfall
  })

  it('renders anomaly severity/variable breakdown and latest anomalies feed from real data', () => {
    mockAllHooks({
      overview: baseQueryResult(POPULATED_OVERVIEW),
      anomalies: baseQueryResult({
        total_anomalies: 2,
        by_variable_severity: [{ variable: 'rainfall', severity: 'CRITICAL', count: 2 }],
        by_severity: [{ severity: 'CRITICAL', count: 2 }],
        by_month: [],
        by_source: [{ source: 'ERA5', count: 2 }],
        by_variable: [{ variable: 'rainfall', count: 2 }],
        latest: [
          {
            id: 'a1',
            source: 'ERA5',
            observed_at: '2024-07-08T08:00:00Z',
            variable: 'rainfall',
            observed_value: 55.2,
            baseline_value: 4.1,
            severity: 'CRITICAL',
            explanation: 'Rainfall far exceeds seasonal baseline',
            latitude: 23.25,
            longitude: 80.0,
            location_name: 'Jabalpur, Madhya Pradesh',
          },
        ],
      }),
    })
    renderWithProviders(<WeatherIntelligenceSection />)

    expect(screen.getByText('Latest anomalies')).toBeInTheDocument()
    expect(screen.getByText(/Rainfall — ERA5/)).toBeInTheDocument()
    expect(screen.getByText('Critical: 2')).toBeInTheDocument()
  })

  it('falls back to raw coordinates when an anomaly has no location_name (real ingested data has none)', () => {
    mockAllHooks({
      overview: baseQueryResult(POPULATED_OVERVIEW),
      anomalies: baseQueryResult({
        total_anomalies: 1,
        by_variable_severity: [{ variable: 'temperature', severity: 'LOW', count: 1 }],
        by_severity: [{ severity: 'LOW', count: 1 }],
        by_month: [],
        by_source: [{ source: 'Open-Meteo', count: 1 }],
        by_variable: [{ variable: 'temperature', count: 1 }],
        latest: [
          {
            id: 'a2',
            source: 'Open-Meteo',
            observed_at: '2024-03-02T05:00:00Z',
            variable: 'temperature',
            observed_value: 12.0,
            baseline_value: 20.0,
            severity: 'LOW',
            explanation: 'Below seasonal baseline',
            latitude: 23.233742,
            longitude: 80.0,
            location_name: null,
          },
        ],
      }),
    })
    renderWithProviders(<WeatherIntelligenceSection />)

    expect(screen.getByText(/23\.23, 80\.00/)).toBeInTheDocument()
  })

  it('never renders any verify/reject/decision control — this panel is strictly read-only', () => {
    mockAllHooks({ overview: baseQueryResult(POPULATED_OVERVIEW) })
    renderWithProviders(<WeatherIntelligenceSection />)

    expect(screen.queryByRole('button', { name: /verify/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /submit decision/i })).not.toBeInTheDocument()
  })
})
