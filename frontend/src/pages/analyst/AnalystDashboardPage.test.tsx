import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AnalystDashboardPage } from '@/pages/analyst/AnalystDashboardPage'
import * as analyticsHooks from '@/features/analytics/useAnalytics'

describe('AnalystDashboardPage', () => {
  it('shows a loading state initially', () => {
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
