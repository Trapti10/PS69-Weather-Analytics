import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidenceStatusBadge, FinalStatusBadge } from '@/components/ui/StatusBadge'

describe('StatusBadge', () => {
  it('renders CONFLICTING evidence as "Conflicting", never as "Fake" or "Rejected"', () => {
    render(<EvidenceStatusBadge status="CONFLICTING" />)
    expect(screen.getByText('Conflicting')).toBeInTheDocument()
    expect(screen.queryByText(/fake/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/rejected/i)).not.toBeInTheDocument()
  })

  it('renders each evidence status with its own distinct label', () => {
    const cases: [Parameters<typeof EvidenceStatusBadge>[0]['status'], string][] = [
      ['SUPPORTED', 'Supported'],
      ['CONFLICTING', 'Conflicting'],
      ['UNVERIFIED', 'Unverified'],
      ['INSUFFICIENT_EVIDENCE', 'Insufficient Evidence'],
    ]
    for (const [status, label] of cases) {
      const { unmount } = render(<EvidenceStatusBadge status={status} />)
      expect(screen.getByText(label)).toBeInTheDocument()
      unmount()
    }
  })

  it('renders final verification statuses independently of evidence status', () => {
    render(<FinalStatusBadge status="NEEDS_REVIEW" />)
    expect(screen.getByText('Needs Review')).toBeInTheDocument()
  })
})
