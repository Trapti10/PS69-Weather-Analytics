import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/renderWithProviders'
import { RoleRoute } from '@/app/router/RoleRoute'
import { setAuthStorage } from '@/lib/authStorage'

function AdminOnlyPage() {
  return <div>Admin only content</div>
}

describe('RoleRoute', () => {
  it('shows Access Denied when the authenticated user has the wrong role', () => {
    setAuthStorage({ accessToken: 'fake-token', userId: 'u1', email: 'citizen@test.com', role: 'CITIZEN' })

    renderWithProviders(
      <Routes>
        <Route
          path="/admin"
          element={
            <RoleRoute allow={['ADMIN']}>
              <AdminOnlyPage />
            </RoleRoute>
          }
        />
      </Routes>,
      { route: '/admin' }
    )

    expect(screen.getByText('Access denied')).toBeInTheDocument()
    expect(screen.queryByText('Admin only content')).not.toBeInTheDocument()
  })

  it('renders the page content when the role is allowed', () => {
    setAuthStorage({ accessToken: 'fake-token', userId: 'u1', email: 'admin@test.com', role: 'ADMIN' })

    renderWithProviders(
      <Routes>
        <Route
          path="/admin"
          element={
            <RoleRoute allow={['ADMIN']}>
              <AdminOnlyPage />
            </RoleRoute>
          }
        />
      </Routes>,
      { route: '/admin' }
    )

    expect(screen.getByText('Admin only content')).toBeInTheDocument()
  })
})
