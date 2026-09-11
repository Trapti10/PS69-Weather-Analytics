import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardBody } from '@/components/ui/Card'
import { Table, type TableColumn } from '@/components/ui/Table'
import { Pagination } from '@/components/ui/Pagination'
import { Button } from '@/components/ui/Button'
import { LoadingState, EmptyState, ErrorState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge } from '@/components/ui/StatusBadge'
import { Badge } from '@/components/ui/Badge'
import { useMyReports } from '@/features/reports/useReports'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime, truncate } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import type { ReportStatusResponse } from '@/types/domain'

const PAGE_SIZE = 10

const REPORT_VERIFICATION_TONE: Record<string, 'muted' | 'success' | 'danger' | 'warning'> = {
  UNVERIFIED: 'muted',
  VERIFIED: 'success',
  REJECTED: 'danger',
  SUSPICIOUS: 'warning',
}

export function MyReportsPage() {
  const [offset, setOffset] = useState(0)
  // Poll gently so a report's evidence status updates without a manual refresh,
  // as it gets corroborated against other sources shortly after submission.
  const { data, isLoading, isError, error, refetch } = useMyReports({ limit: PAGE_SIZE, offset, poll: true })

  const columns: TableColumn<ReportStatusResponse>[] = [
    {
      key: 'text',
      header: 'Report',
      render: (r) => <span className="text-foreground">{truncate(r.text, 60)}</span>,
    },
    {
      key: 'event_type',
      header: 'Category',
      render: (r) => EVENT_TYPE_LABEL[r.event_type] ?? r.event_type,
    },
    {
      key: 'location',
      header: 'Location',
      render: (r) => [r.city, r.state].filter(Boolean).join(', '),
    },
    {
      key: 'evidence_status',
      header: 'Evidence',
      render: (r) => (r.evidence_status ? <EvidenceStatusBadge status={r.evidence_status} /> : <span className="text-muted">—</span>),
    },
    {
      key: 'verification_status',
      header: 'Report Status',
      render: (r) => <Badge tone={REPORT_VERIFICATION_TONE[r.verification_status] ?? 'muted'}>{r.verification_status}</Badge>,
    },
    {
      key: 'final_verification_status',
      header: 'Event Decision',
      render: (r) =>
        r.final_verification_status ? (
          <FinalStatusBadge status={r.final_verification_status} />
        ) : (
          <span className="text-muted">—</span>
        ),
    },
    {
      key: 'created_at',
      header: 'Submitted',
      render: (r) => formatDateTime(r.created_at),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">My reports</h1>
          <p className="text-sm text-muted">Reports you've personally submitted, and their current status.</p>
        </div>
        <Link to="/citizen/report">
          <Button size="sm">Submit a new report</Button>
        </Link>
      </div>

      <Card>
        <CardBody>
          {isLoading && <LoadingState label="Loading your reports" rows={4} />}

          {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}

          {!isLoading && !isError && data && data.reports.length === 0 && (
            <EmptyState
              title="You haven't submitted any reports yet"
              description="Once you submit a weather report, it will show up here with its evidence status and final event decision."
              action={
                <Link to="/citizen/report">
                  <Button size="sm">Submit your first report</Button>
                </Link>
              }
            />
          )}

          {!isLoading && !isError && data && data.reports.length > 0 && (
            <>
              <Table columns={columns} rows={data.reports} getRowKey={(r) => r.report_id} />
              <Pagination total={data.total} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
