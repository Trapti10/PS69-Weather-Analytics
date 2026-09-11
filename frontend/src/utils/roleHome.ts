import type { UserRole } from '@/types/domain'

export function homePathForRole(role: UserRole): string {
  switch (role) {
    case 'ADMIN':
      return '/admin'
    case 'ANALYST':
      return '/analyst'
    case 'CITIZEN':
    default:
      return '/citizen'
  }
}
