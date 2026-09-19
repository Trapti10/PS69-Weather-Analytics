import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/renderWithProviders'
import { LoginPage } from '@/pages/auth/LoginPage'
import * as authApi from '@/services/api/auth'

function CitizenHomeStub() {
  return <div>Citizen home</div>
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('logs in successfully and navigates to the citizen home', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'token123',
      refresh_token: 'refresh123',
      token_type: 'bearer',
      user_id: 'user-1',
      role: 'CITIZEN',
      expires_in: 86400,
    })

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/citizen" element={<CitizenHomeStub />} />
      </Routes>,
      { route: '/login' }
    )

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'citizen@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByText('Citizen home')).toBeInTheDocument())
    expect(localStorage.getItem('ps69_access_token')).toBe('token123')
  })

  it('shows an error message when login fails', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue({
      isAxiosError: true,
      response: { status: 401, data: { detail: 'Invalid email or password' } },
    })

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>,
      { route: '/login' }
    )

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'wrong@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
