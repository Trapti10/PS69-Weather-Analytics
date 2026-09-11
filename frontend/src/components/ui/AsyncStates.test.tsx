import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/AsyncStates'

describe('AsyncStates', () => {
  it('LoadingState renders a status region for screen readers', () => {
    render(<LoadingState label="Loading events" />)
    expect(screen.getByText('Loading events')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('EmptyState renders title, description and an optional action', () => {
    render(
      <EmptyState
        title="No reports yet"
        description="Submit your first report."
        action={<button>Submit</button>}
      />
    )
    expect(screen.getByText('No reports yet')).toBeInTheDocument()
    expect(screen.getByText('Submit your first report.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument()
  })

  it('ErrorState renders the message and calls onRetry when clicked', () => {
    const onRetry = vi.fn()
    render(<ErrorState message="Network error — check your connection." onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Network error')
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
