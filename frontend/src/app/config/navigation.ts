import type { UserRole } from '@/types/domain'

export interface NavItem {
  label: string
  to: string
  end?: boolean
}

export const NAV_ITEMS_BY_ROLE: Record<UserRole, NavItem[]> = {
  CITIZEN: [
    { label: 'Dashboard', to: '/citizen', end: true },
    { label: 'Submit Report', to: '/citizen/report' },
    { label: 'My Reports', to: '/citizen/reports' },
    { label: 'Weather Events', to: '/citizen/events' },
    { label: 'Map', to: '/citizen/map' },
  ],
  ANALYST: [
    { label: 'Dashboard', to: '/analyst', end: true },
    { label: 'Weather Events', to: '/analyst/events' },
    { label: 'Analytics', to: '/analyst/analytics' },
    { label: 'Map', to: '/analyst/map' },
  ],
  ADMIN: [
    { label: 'Dashboard', to: '/admin', end: true },
    { label: 'Verification Queue', to: '/admin/verification' },
  ],
}

export const ROLE_LABEL: Record<UserRole, string> = {
  CITIZEN: 'Citizen',
  ANALYST: 'Analyst',
  ADMIN: 'Administrator',
}
