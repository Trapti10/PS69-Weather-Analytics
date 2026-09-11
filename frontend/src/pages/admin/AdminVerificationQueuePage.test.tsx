import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AdminVerificationQueuePage } from '@/pages/admin/AdminVerificationQueuePage'
import * as verificationModule from '@/features/verification/useVerification'

describe('AdminVerificationQueuePage', () => {
  it('shows a loading state initially', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AdminVerificationQueuePage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders queue entries with their evidence and verification statuses', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue').mockReturnValue({
      data: {
        items: [
          {
            event_id: 'e1',
            event_type: 'FLOODING',
            location_name: 'Jabalpur, Madhya Pradesh',
            severity: 'MEDIUM',
            start_time: '2026-01-01T10:00:00Z',
            evidence_status: 'CONFLICTING',
            evidence_support_score: 0.4,
            final_verification_status: 'NEEDS_REVIEW',
            report_count: 3,
            created_at: '2026-01-01T10:00:00Z',
            updated_at: '2026-01-01T10:05:00Z',
          },
        ],
        total: 1,
        limit: 15,
        offset: 0,
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AdminVerificationQueuePage />)
    const table = screen.getByRole('table')
    expect(within(table).getByText('Jabalpur, Madhya Pradesh')).toBeInTheDocument()
    expect(within(table).getByText('Conflicting')).toBeInTheDocument()
    expect(within(table).getByText('Needs Review')).toBeInTheDocument()
    // Evidence status must never be conflated with final verification status.
    expect(within(table).queryByText('Rejected')).not.toBeInTheDocument()
  })

  it('shows an empty state when nothing matches the filters', () => {
    vi.spyOn(verificationModule, 'useVerificationQueue').mockReturnValue({
      data: { items: [], total: 0, limit: 15, offset: 0 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)

    renderWithProviders(<AdminVerificationQueuePage />)
    expect(screen.getByText(/nothing to review/i)).toBeInTheDocument()
  })
})
