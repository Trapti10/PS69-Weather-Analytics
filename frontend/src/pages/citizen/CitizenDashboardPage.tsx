import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge } from '@/components/ui/StatusBadge'
import { useMyReports } from '@/features/reports/useReports'
import { useAuth } from '@/hooks/useAuth'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime, truncate } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import type { ReportStatusResponse } from '@/types/domain'

export function CitizenDashboardPage() {
  const { user } = useAuth()
  const { data, isLoading, isError, error, refetch } = useMyReports({ limit: 5, offset: 0 })

  const verifiedCount = data?.reports.filter((r: ReportStatusResponse) => r.final_verification_status === 'VERIFIED').length ?? 0
  const supportedCount = data?.reports.filter((r: ReportStatusResponse) => r.evidence_status === 'SUPPORTED').length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Welcome{user ? `, ${user.email}` : ''}</h1>
        <p className="text-sm text-muted">Here's an overview of your recent weather reporting activity.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Reports submitted" value={data?.total ?? (isLoading ? '—' : 0)} />
        <StatCard label="Verified events" value={verifiedCount} tone="success" />
        <StatCard label="Evidence supported" value={supportedCount} tone="success" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/citizen/report">
          <Button className="w-full" size="lg">
            Submit a report
          </Button>
        </Link>
        <Link to="/citizen/reports">
          <Button variant="outline" className="w-full" size="lg">
            View my reports
          </Button>
        </Link>
        <Link to="/citizen/map">
          <Button variant="outline" className="w-full" size="lg">
            View event map
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent reports</CardTitle>
        </CardHeader>
        <CardBody>
          {isLoading && <LoadingState label="Loading recent reports" rows={3} />}
          {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}
          {!isLoading && !isError && data && data.reports.length === 0 && (
            <EmptyState
              title="No reports yet"
              description="Submit your first weather report to see it here."
              action={
                <Link to="/citizen/report">
                  <Button size="sm">Submit a report</Button>
                </Link>
              }
            />
          )}
          {!isLoading && !isError && data && data.reports.length > 0 && (
            <ul className="flex flex-col divide-y divide-border">
              {data.reports.map((r) => (
                <li key={r.report_id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{truncate(r.text, 70)}</p>
                    <p className="text-xs text-muted">
                      {EVENT_TYPE_LABEL[r.event_type] ?? r.event_type} · {r.city} · {formatDateTime(r.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-1">
                    {r.evidence_status && <EvidenceStatusBadge status={r.evidence_status} />}
                    {r.final_verification_status && <FinalStatusBadge status={r.final_verification_status} />}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
