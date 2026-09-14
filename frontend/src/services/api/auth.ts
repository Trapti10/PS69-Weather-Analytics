import { apiClient } from '@/services/api/client'
import type { TokenResponse, UserRole } from '@/types/domain'

export interface LoginPayload {
  email: string
  password: string
  /**
   * The account type selected on the "Login as" dropdown. This is sent to
   * the backend purely as a check - the backend rejects login if it
   * doesn't match the account's actual role (see
   * backend/api/routes/auth.py:login). It never grants a role: the role
   * that ends up in the JWT/auth state is always TokenResponse.role,
   * returned by the backend, not this value.
   */
  role: UserRole
}

export interface RegisterPayload {
  email: string
  password: string
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function register(payload: RegisterPayload): Promise<TokenResponse> {
  // Public registration always creates CITIZEN accounts (enforced server-side).
  const { data } = await apiClient.post<TokenResponse>('/auth/register', {
    ...payload,
    role: 'CITIZEN',
  })
  return data
}
