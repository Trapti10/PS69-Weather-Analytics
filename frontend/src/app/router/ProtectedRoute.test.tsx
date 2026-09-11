import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '@/test/renderWithProviders'
import { ProtectedRoute } from '@/app/router/ProtectedRoute'

function SecretPage() {
  return <div>Secret content</div>
}

function LoginStub() {
  return <div>Login page</div>
}

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users to /login', () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginStub />} />
        <Route
          path="/secret"
          element={
            <ProtectedRoute>
              <SecretPage />
            </ProtectedRoute>
          }
        />
      </Routes>,
      { route: '/secret' }
    )

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })
})
