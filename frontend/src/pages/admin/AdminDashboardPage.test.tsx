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
    })
  )
  vi.spyOn(analyticsHooks, 'useWeatherTrends').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useTemperatureAnalytics').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useRainfallAnalytics').mockReturnValue(emptyAnalyticsResult({ trends: [] }))
  vi.spyOn(analyticsHooks, 'useSourceComparison').mockReturnValue(emptyAnalyticsResult({ sources: [] }))
  vi.spyOn(analyticsHooks, 'useAnomalies').mockReturnValue(
    emptyAnalyticsResult({ total_anomalies: 0, by_variable_severity: [], by_severity: [], latest: [] })
  )
  vi.spyOn(analyticsHooks, 'useEventDistribution').mockReturnValue(
    emptyAnalyticsResult({ total_events: 0, by_event_type: [], by_severity: [] })
  )
  vi.spyOn(analyticsHooks, 'useVerificationAnalytics').mockReturnValue(
    emptyAnalyticsResult({ total_events: 0, verified: 0, needs_review: 0, rejected: 0 })
  )
}

describe('AdminDashboardPage', () => {
  it('shows both the operational verification counts and the weather intelligence section', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue')
      .mockReturnValueOnce(queueResult(4)) // needs review
      .mockReturnValueOnce(queueResult(9)) // verified
      .mockReturnValueOnce(queueResult(1)) // rejected
    mockIntelligenceHooksAsEmpty()

    renderWithProviders(<AdminDashboardPage />)

    // Operational counts (existing Phase 6 behavior, unchanged)
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
