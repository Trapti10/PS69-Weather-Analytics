import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'

export function AccessDeniedPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-bg text-danger">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path strokeLinecap="round" d="M4.93 4.93l14.14 14.14" />
        </svg>
      </div>
      <h1 className="text-lg font-semibold text-foreground">Access denied</h1>
      <p className="max-w-sm text-sm text-muted">
        Your account doesn't have permission to view this page. If you think this is a mistake, contact an
        administrator.
      </p>
      <Link to="/">
        <Button variant="outline" size="sm">
          Back to dashboard
        </Button>
      </Link>
    </div>
  )
}
