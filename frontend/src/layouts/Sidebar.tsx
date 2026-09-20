import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { NAV_ITEMS_BY_ROLE, ROLE_LABEL } from '@/app/config/navigation'
import type { UserRole } from '@/types/domain'
import { WeatherGlyph, type WeatherGlyphName } from '@/components/common/WeatherGlyph'

export interface SidebarProps {
  role: UserRole
  open: boolean
  onNavigate?: () => void
}

const NAV_ICON: Record<string, WeatherGlyphName> = {
  'Command Center': 'dashboard',
  'Operations Center': 'dashboard',
  'Dashboard': 'dashboard',
  'Submit Report': 'event',
  'My Reports': 'research',
  'Weather Events': 'event',
  'Weather Analytics': 'forecast',
  'Research Data': 'database',
  'Live Map': 'map',
  'Verification Queue': 'shield',
  'Map': 'map',
}

export function Sidebar({ role, open, onNavigate }: SidebarProps) {
  const items = NAV_ITEMS_BY_ROLE[role]

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen w-64 shrink-0 transform flex-col overflow-y-auto overscroll-contain border-r border-border bg-surface transition-transform duration-200 md:sticky md:top-0 md:self-start md:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full'
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-16 items-center gap-3 border-b border-border px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/20">
          <WeatherGlyph name="cloud" className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-primary">Weather</p>
          <p className="text-sm font-semibold text-foreground">Intelligence</p>
        </div>
      </div>

      <div className="border-b border-border px-4 py-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Current role</p>
        <div className="mt-2 flex items-center gap-2 rounded-xl border border-border bg-surface-muted px-3 py-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <WeatherGlyph name={role === 'ADMIN' ? 'shield' : role === 'ANALYST' ? 'research' : 'event'} className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-foreground">{ROLE_LABEL[role]}</p>
            <p className="text-[10px] text-muted">Authenticated workspace</p>
          </div>
          <span className="ml-auto h-2 w-2 rounded-full bg-success animate-pulse-soft" />
        </div>
      </div>

      <p className="px-5 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
        {role === 'CITIZEN' ? 'My Weather' : role === 'ANALYST' ? 'Intelligence Desk' : 'Operations'}
      </p>
      <nav className="flex flex-col gap-1 px-3 pb-5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary/12 text-primary shadow-[inset_3px_0_0_var(--color-primary)]'
                  : 'text-muted hover:bg-surface-hover hover:text-foreground'
              )
            }
          >
            <WeatherGlyph name={NAV_ICON[item.label] ?? 'dashboard'} className="h-4 w-4 shrink-0 transition-transform duration-200 group-hover:scale-105" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
