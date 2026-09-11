import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'
import { ROLE_LABEL } from '@/app/config/navigation'

export interface TopbarProps {
  onMenuToggle: () => void
  title?: string
}

export function Topbar({ onMenuToggle, title }: TopbarProps) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-surface px-4 md:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuToggle}
          className="rounded-[var(--radius-sm)] p-2 text-muted hover:bg-surface-hover hover:text-foreground md:hidden"
          aria-label="Toggle navigation menu"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        {title && <h1 className="text-sm font-semibold text-foreground md:text-base">{title}</h1>}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleTheme}
          className="rounded-[var(--radius-sm)] p-2 text-muted hover:bg-surface-hover hover:text-foreground"
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="4" />
              <path strokeLinecap="round" d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
            </svg>
          )}
        </button>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 hover:bg-surface-hover"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
              {user?.email?.charAt(0).toUpperCase() ?? '?'}
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-xs font-medium text-foreground">{user?.email}</p>
              <p className="text-[11px] text-muted">{user ? ROLE_LABEL[user.role] : ''}</p>
            </div>
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-44 rounded-[var(--radius-md)] border border-border bg-surface p-1 shadow-[var(--shadow-md)]"
            >
              <button
                role="menuitem"
                onClick={handleLogout}
                className="w-full rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm text-danger hover:bg-danger-bg"
              >
                Log out
              </button>
            </div>
          )}
        </div>

        <Button variant="outline" size="sm" className="hidden md:inline-flex" onClick={handleLogout}>
          Log out
        </Button>
      </div>
    </header>
  )
}
