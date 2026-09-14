import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/renderWithProviders'
import { LoginPage } from '@/pages/auth/LoginPage'
import * as authApi from '@/services/api/auth'

function CitizenHomeStub() {
  return <div>Citizen home</div>
}
function AnalystHomeStub() {
  return <div>Analyst home</div>
}
function AdminHomeStub() {
  return <div>Admin home</div>
}

function renderLogin() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/citizen" element={<CitizenHomeStub />} />
      <Route path="/analyst" element={<AnalystHomeStub />} />
      <Route path="/admin" element={<AdminHomeStub />} />
    </Routes>,
    { route: '/login' }
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('defaults the "Login as" dropdown to Citizen', () => {
    renderLogin()
    expect(screen.getByLabelText(/login as/i)).toHaveValue('CITIZEN')
  })

  it('shows all three role options with the correct display labels', () => {
    renderLogin()
    const select = screen.getByLabelText(/login as/i) as HTMLSelectElement
    const optionText = Array.from(select.options).map((o) => o.textContent)
    expect(optionText).toEqual(['Citizen', 'Analyst / Researcher', 'Administrator'])
  })

  it('logs in successfully with the default (Citizen) role and navigates to the citizen home', async () => {
    const loginSpy = vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'token123',
      refresh_token: 'refresh123',
      token_type: 'bearer',
      user_id: 'user-1',
      role: 'CITIZEN',
      expires_in: 86400,
    })

    renderLogin()

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'citizen@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByText('Citizen home')).toBeInTheDocument())
    expect(localStorage.getItem('ps69_access_token')).toBe('token123')
    expect(loginSpy).toHaveBeenCalledWith({ email: 'citizen@test.com', password: 'password123', role: 'CITIZEN' })
  })

  it('sends the selected Analyst role and navigates to the analyst home on success', async () => {
    const loginSpy = vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'analyst-token',
      refresh_token: 'analyst-refresh',
      token_type: 'bearer',
      user_id: 'user-2',
      role: 'ANALYST',
      expires_in: 86400,
    })

    renderLogin()
    fireEvent.change(screen.getByLabelText(/login as/i), { target: { value: 'ANALYST' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'analyst@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByText('Analyst home')).toBeInTheDocument())
    expect(loginSpy).toHaveBeenCalledWith({ email: 'analyst@test.com', password: 'password123', role: 'ANALYST' })
  })

  it('sends the selected Administrator role and navigates to the admin home on success', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'admin-token',
      refresh_token: 'admin-refresh',
      token_type: 'bearer',
      user_id: 'user-3',
      role: 'ADMIN',
      expires_in: 86400,
    })

    renderLogin()
    fireEvent.change(screen.getByLabelText(/login as/i), { target: { value: 'ADMIN' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'admin@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByText('Admin home')).toBeInTheDocument())
  })

  it('shows the exact role-mismatch message from the backend when credentials are correct but the wrong role was selected', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 403,
        data: { detail: 'These credentials belong to a different role. Please select the correct login type.' },
      },
    })

    renderLogin()
    fireEvent.change(screen.getByLabelText(/login as/i), { target: { value: 'ADMIN' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'citizen@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'These credentials belong to a different role. Please select the correct login type.'
      )
    )
    // Never navigated anywhere - no dashboard stub rendered.
    expect(screen.queryByText(/home$/)).not.toBeInTheDocument()
  })

  it('shows the exact invalid-credentials message on wrong password, not a generic session-expired message', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue({
      isAxiosError: true,
      response: { status: 401, data: { detail: 'Invalid email or password' } },
    })

    renderLogin()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'wrong@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid email or password'))
  })

  it('falls back to a generic message for a network error with no response body', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue({ isAxiosError: true, response: undefined })

    renderLogin()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'x@test.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
