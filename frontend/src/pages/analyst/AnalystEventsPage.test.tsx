import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AnalystEventsPage } from '@/pages/analyst/AnalystEventsPage'
import * as eventsModule from '@/features/events/useEvents'

describe('AnalystEventsPage (read-only)', () => {
  it('renders event data without any verification decision controls', () => {
    vi.spyOn(eventsModule, 'useEvents').mockReturnValue({
      data: {
        events: [
          {
            event_id: 'e1',
            event_type: 'HEATWAVE',
            location_name: 'Bhopal, Madhya Pradesh',
            severity: 'HIGH',
            start_time: '2026-01-01T10:00:00Z',
            end_time: null,
            latitude: 23.25,
            longitude: 77.41,
            evidence_status: 'SUPPORTED',
            evidence_support_score: 0.9,
            evidence_detail: null,
            final_verification_status: 'VERIFIED',
            report_count: 5,
            unique_sources: 3,
            member_report_ids: [],
            reviewed_by: null,
            reviewed_at: null,
            review_notes: null,
            created_at: '2026-01-01T10:00:00Z',
            updated_at: '2026-01-01T10:00:00Z',
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

    renderWithProviders(<AnalystEventsPage />)

    expect(screen.getByText('Bhopal, Madhya Pradesh')).toBeInTheDocument()
    // Analyst view must never expose admin verification decision controls.
    expect(screen.queryByRole('button', { name: /submit decision/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/decision/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/verification decision/i)).not.toBeInTheDocument()
  })
})
