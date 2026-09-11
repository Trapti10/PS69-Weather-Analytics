import type { AuthUser, UserRole } from '@/types/domain'

const ACCESS_TOKEN_KEY = 'ps69_access_token'
const REFRESH_TOKEN_KEY = 'ps69_refresh_token'
const USER_KEY = 'ps69_user'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function setAuthStorage(params: {
  accessToken: string
  refreshToken?: string | null
  userId: string
  email: string
  role: UserRole
}): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, params.accessToken)
  if (params.refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, params.refreshToken)
  }
  const user: AuthUser = { user_id: params.userId, email: params.email, role: params.role }
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuthStorage(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
