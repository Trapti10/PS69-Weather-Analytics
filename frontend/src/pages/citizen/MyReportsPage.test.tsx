import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { MyReportsPage } from '@/pages/citizen/MyReportsPage'
import * as useReportsModule from '@/features/reports/useReports'

describe('MyReportsPage', () => {
  it('shows a loading state while fetching', () => {
    vi.spyOn(useReportsModule, 'useMyReports').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<MyReportsPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows an error state with retry on failure', () => {
    vi.spyOn(useReportsModule, 'useMyReports').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { isAxiosError: true, response: { status: 500 } },
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<MyReportsPage />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows an empty state when there are no reports', () => {
    vi.spyOn(useReportsModule, 'useMyReports').mockReturnValue({
      data: { reports: [], total: 0, limit: 10, offset: 0 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<MyReportsPage />)
    expect(screen.getByText(/haven't submitted any reports yet/i)).toBeInTheDocument()
  })

  it('renders real report data in the table', () => {
    vi.spyOn(useReportsModule, 'useMyReports').mockReturnValue({
      data: {
        reports: [
          {
            report_id: 'r1',
            source_type: 'CITIZEN_REPORT',
            text: 'Heavy rainfall near the market',
            city: 'Jabalpur',
            state: 'Madhya Pradesh',
            event_type: 'FLOODING',
            verification_status: 'UNVERIFIED',
            evidence_status: 'INSUFFICIENT_EVIDENCE',
            evidence_support_score: null,
            created_at: '2026-01-01T10:00:00Z',
            updated_at: '2026-01-01T10:00:00Z',
            event_id: 'e1',
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<MyReportsPage />)
    expect(screen.getByText(/heavy rainfall near the market/i)).toBeInTheDocument()
    expect(screen.getByText('Flooding')).toBeInTheDocument()
    expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument()
  })
})
