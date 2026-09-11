import { describe, expect, it, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '@testing-library/react'
import { ReportForm } from '@/components/forms/ReportForm'

describe('ReportForm', () => {
  it('shows validation errors when required fields are missing', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(screen.getByText(/please describe what you observed/i)).toBeInTheDocument()
    expect(screen.getByText(/city is required/i)).toBeInTheDocument()
    expect(screen.getByText(/please select an event type/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits a well-formed payload matching the backend contract', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText(/what did you observe/i), {
      target: { value: 'Heavy rainfall and street flooding near the market' },
    })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'FLOODING' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Jabalpur' } })
    fireEvent.change(screen.getByLabelText(/state/i), { target: { value: 'Madhya Pradesh' } })
    fireEvent.change(screen.getByLabelText(/latitude/i), { target: { value: '23.1815' } })
    fireEvent.change(screen.getByLabelText(/longitude/i), { target: { value: '79.9864' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(onSubmit).toHaveBeenCalledWith({
      text: 'Heavy rainfall and street flooding near the market',
      city: 'Jabalpur',
      state: 'Madhya Pradesh',
      latitude: 23.1815,
      longitude: 79.9864,
      event_type: 'FLOODING',
    })
  })

  it('rejects a non-numeric latitude', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText(/what did you observe/i), {
      target: { value: 'Strong winds knocked down a tree' },
    })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'STRONG_WIND' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Bhopal' } })
    fireEvent.change(screen.getByLabelText(/latitude/i), { target: { value: 'not-a-number' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(screen.getByText(/latitude must be a number/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects description text shorter than the backend minimum of 10 characters', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    // 9 characters — one short of the backend's ReportSubmissionRequest min_length=10.
    fireEvent.change(screen.getByLabelText(/what did you observe/i), { target: { value: 'Too short' } })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'FOG' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Indore' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('accepts description text at exactly the backend minimum of 10 characters', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText(/what did you observe/i), { target: { value: '1234567890' } })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'FOG' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Indore' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ text: '1234567890' }))
  })

  it('requires longitude when latitude is provided, matching the backend validator', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText(/what did you observe/i), {
      target: { value: 'Dust storm reducing visibility on the highway' },
    })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'DUST_STORM' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Gwalior' } })
    fireEvent.change(screen.getByLabelText(/latitude/i), { target: { value: '26.2183' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(screen.getByText(/longitude is required when latitude is provided/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects a latitude outside the backend-allowed range of -90 to 90', () => {
    const onSubmit = vi.fn()
    render(<ReportForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText(/what did you observe/i), {
      target: { value: 'Heatwave conditions across the district' },
    })
    fireEvent.change(screen.getByLabelText(/event type/i), { target: { value: 'HEATWAVE' } })
    fireEvent.change(screen.getByLabelText(/city/i), { target: { value: 'Bhopal' } })
    fireEvent.change(screen.getByLabelText(/latitude/i), { target: { value: '120' } })
    fireEvent.change(screen.getByLabelText(/longitude/i), { target: { value: '77.4' } })

    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(screen.getByText(/latitude must be between -90 and 90/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
