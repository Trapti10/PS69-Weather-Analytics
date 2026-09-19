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
    { label: 'Command Center', to: '/analyst', end: true },
    { label: 'Weather Analytics', to: '/analyst/analytics' },
    { label: 'Weather Events', to: '/analyst/events' },
    { label: 'Research Data', to: '/analyst/data' },
    { label: 'Live Map', to: '/analyst/map' },
  ],
  ADMIN: [
    { label: 'Operations Center', to: '/admin', end: true },
    { label: 'Verification Queue', to: '/admin/verification' },
    { label: 'Weather Events', to: '/admin/events' },
    { label: 'Live Map', to: '/admin/map' },
  ],
}

export const ROLE_LABEL: Record<UserRole, string> = {
  CITIZEN: 'Citizen',
  ANALYST: 'Analyst / Researcher',
  ADMIN: 'Administrator',
}
