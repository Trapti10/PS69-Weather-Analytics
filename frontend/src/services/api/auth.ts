import { apiClient } from '@/services/api/client'
import type { TokenResponse } from '@/types/domain'

export interface LoginPayload {
  email: string
  password: string
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
