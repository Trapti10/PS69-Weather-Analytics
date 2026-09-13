import { Link } from 'react-router-dom'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState } from '@/components/ui/AsyncStates'
import { useAnalyticsOverview } from '@/features/analytics/useAnalytics'
import { normalizeApiError } from '@/services/api/client'

export function AnalystDashboardPage() {
  const { data, isLoading, isError, error, refetch } = useAnalyticsOverview()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">National Weather Intelligence</h1>
        <p className="text-sm text-muted">
          A read-only snapshot of the collected weather data and event activity. Every figure is aggregated in the
          database.
        </p>
      </div>

      {isLoading && <LoadingState label="Loading dashboard" rows={2} />}
      {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}

      {!isLoading && !isError && data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Weather observations" value={data.total_weather_observations.toLocaleString()} />
          <StatCard label="Weather events" value={data.total_weather_events.toLocaleString()} />
          <StatCard label="Detected anomalies" value={data.total_anomalies.toLocaleString()} tone="warning" />
          <StatCard label="Verified events" value={data.verified_events} tone="success" />
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
            View full intelligence
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
