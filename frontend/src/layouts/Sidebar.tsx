import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { NAV_ITEMS_BY_ROLE } from '@/app/config/navigation'
import type { UserRole } from '@/types/domain'

export interface SidebarProps {
  role: UserRole
  open: boolean
  onNavigate?: () => void
}

export function Sidebar({ role, open, onNavigate }: SidebarProps) {
  const items = NAV_ITEMS_BY_ROLE[role]

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 w-64 shrink-0 transform border-r border-border bg-surface transition-transform duration-200 md:static md:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full'
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-16 items-center gap-2 border-b border-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-primary/15 text-primary font-bold">
          W
        </div>
        <span className="text-sm font-semibold text-foreground">Weather Intelligence</span>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted hover:bg-surface-hover hover:text-foreground'
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
