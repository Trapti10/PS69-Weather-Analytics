import { Link } from 'react-router-dom'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState } from '@/components/ui/AsyncStates'
import { useAnalytics } from '@/features/analytics/useAnalytics'
import { normalizeApiError } from '@/services/api/client'

export function AnalystDashboardPage() {
  const { summary, isLoading, isError, error, refetch } = useAnalytics()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Analyst dashboard</h1>
        <p className="text-sm text-muted">A read-only snapshot of current weather event activity.</p>
      </div>

      {isLoading && <LoadingState label="Loading dashboard" rows={2} />}
      {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}

      {!isLoading && !isError && summary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total events" value={summary.totalEvents} />
          <StatCard label="Verified" value={summary.verifiedCount} tone="success" />
          <StatCard label="Needs review" value={summary.needsReviewCount} tone="warning" />
          <StatCard label="Rejected" value={summary.rejectedCount} tone="danger" />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/analyst/events">
          <Button variant="outline" className="w-full" size="lg">
            Browse events
          </Button>
        </Link>
        <Link to="/analyst/analytics">
          <Button variant="outline" className="w-full" size="lg">
            View analytics
          </Button>
        </Link>
        <Link to="/analyst/map">
          <Button variant="outline" className="w-full" size="lg">
            View event map
          </Button>
        </Link>
      </div>
    </div>
  )
}
