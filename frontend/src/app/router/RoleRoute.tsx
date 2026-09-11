import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { UserRole } from '@/types/domain'
import { AccessDeniedPage } from '@/pages/shared/AccessDeniedPage'

export function RoleRoute({ allow, children }: { allow: UserRole[]; children: ReactNode }) {
  const { user, isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (user && !allow.includes(user.role)) {
    return <AccessDeniedPage />
  }

  return <>{children}</>
}
