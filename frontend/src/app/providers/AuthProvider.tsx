import { createContext, useCallback, useMemo, useState, type ReactNode } from 'react'
import type { AuthUser, UserRole } from '@/types/domain'
import { clearAuthStorage, getAccessToken, getStoredUser, setAuthStorage } from '@/lib/authStorage'

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  hasRole: (...roles: UserRole[]) => boolean
  login: (params: { accessToken: string; refreshToken?: string | null; userId: string; email: string; role: UserRole }) => void
  logout: () => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    // Only trust stored user info if an access token is also present.
    return getAccessToken() ? getStoredUser() : null
  })

  const login = useCallback<AuthContextValue['login']>((params) => {
    setAuthStorage({
      accessToken: params.accessToken,
      refreshToken: params.refreshToken,
      userId: params.userId,
      email: params.email,
      role: params.role,
    })
    setUser({ user_id: params.userId, email: params.email, role: params.role })
  }, [])

  const logout = useCallback(() => {
    clearAuthStorage()
    setUser(null)
  }, [])

  const hasRole = useCallback(
    (...roles: UserRole[]) => !!user && roles.includes(user.role),
    [user]
  )

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: !!user, hasRole, login, logout }),
    [user, hasRole, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
