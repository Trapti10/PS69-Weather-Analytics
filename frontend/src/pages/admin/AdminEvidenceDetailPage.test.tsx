import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AdminEvidenceDetailPage } from '@/pages/admin/AdminEvidenceDetailPage'
import * as verificationModule from '@/features/verification/useVerification'

const mockEvidence = {
  event: {
    event_id: 'e1',
    event_type: 'FLOODING',
    location_name: 'Jabalpur, Madhya Pradesh',
    severity: 'MEDIUM' as const,
    start_time: '2026-01-01T10:00:00Z',
    end_time: null,
    evidence_status: 'CONFLICTING' as const,
    evidence_support_score: 0.4,
    final_verification_status: 'NEEDS_REVIEW' as const,
    report_count: 2,
    unique_sources: 2,
  },
  external_evidence: null,
  reports: [
    {
      report_id: 'r1',
      source_type: 'CITIZEN_REPORT',
      source_name: 'FastAPI_Phase5',
      report_timestamp: '2026-01-01T10:00:00Z',
      city: 'Jabalpur',
      state: 'Madhya Pradesh',
      text: 'Heavy rainfall reported near the market',
      event_type: 'FLOODING',
      verification_status: 'UNVERIFIED' as const,
      source_reliability: 0.4,
      predicted_event_category: 'FLOODING',
      event_classification_confidence: 0.8,
      risk_score: 0.5,
      risk_label: 'MEDIUM',
      semantic_similarity_score: 0.2,
      is_duplicate: false,
      is_suspicious: false,
    },
  ],
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/events/:eventId" element={<AdminEvidenceDetailPage />} />
    </Routes>,
    { route: '/admin/events/e1' }
  )
}

describe('AdminEvidenceDetailPage', () => {
  const mutateMock = vi.fn()

  beforeEach(() => {
    mutateMock.mockReset()
    vi.spyOn(verificationModule, 'useEventEvidence').mockReturnValue({
      data: mockEvidence,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)
    vi.spyOn(verificationModule, 'useVerifyEventMutation').mockReturnValue({
      mutate: mutateMock,
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)
  })

  it('renders event summary and evidence with evidence/final status kept separate', () => {
    renderPage()
    expect(screen.getByText('Conflicting')).toBeInTheDocument()
    expect(screen.getByText('Needs Review')).toBeInTheDocument()
    expect(screen.getByText(/heavy rainfall reported near the market/i)).toBeInTheDocument()
  })

  it('requires notes before confirming a REJECTED decision', () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/decision/i), { target: { value: 'REJECTED' } })
    fireEvent.click(screen.getByRole('button', { name: /submit decision/i }))
    fireEvent.click(screen.getByRole('button', { name: /^confirm reject$/i }))

    expect(screen.getByText(/please provide a reason/i)).toBeInTheDocument()
    expect(mutateMock).not.toHaveBeenCalled()
  })

  it('requires notes before confirming a NEEDS_REVIEW decision', () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/decision/i), { target: { value: 'NEEDS_REVIEW' } })
    fireEvent.click(screen.getByRole('button', { name: /submit decision/i }))
    fireEvent.click(screen.getByRole('button', { name: /^confirm keep needs review$/i }))

    expect(screen.getByText(/please provide a reason/i)).toBeInTheDocument()
    expect(mutateMock).not.toHaveBeenCalled()
  })

  it('submits VERIFIED without requiring notes', () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/decision/i), { target: { value: 'VERIFIED' } })
    fireEvent.click(screen.getByRole('button', { name: /submit decision/i }))
    fireEvent.click(screen.getByRole('button', { name: /^confirm verify$/i }))

    expect(mutateMock).toHaveBeenCalledWith(
      { action: 'VERIFIED', notes: null },
      expect.objectContaining({ onSuccess: expect.any(Function) })
    )
  })
})
