import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Card, CardBody } from '@/components/ui/Card'
import { Table, type TableColumn } from '@/components/ui/Table'
import { Pagination } from '@/components/ui/Pagination'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge, SeverityBadge } from '@/components/ui/StatusBadge'
import { FilterBar, FilterField } from '@/components/common/FilterBar'
import { Input, Select } from '@/components/ui/Field'
import { useVerificationQueue } from '@/features/verification/useVerification'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime } from '@/utils/format'
import { EVENT_TYPE_LABEL, EVIDENCE_STATUS_LABEL } from '@/constants/status'
import type { AdminQueueEntry, EvidenceStatus, EventType, FinalVerificationStatus, Severity } from '@/types/domain'

const PAGE_SIZE = 15

export function AdminVerificationQueuePage() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<FinalVerificationStatus | 'ALL'>('NEEDS_REVIEW')
  const [evidenceStatus, setEvidenceStatus] = useState<EvidenceStatus | ''>('')
  const [eventType, setEventType] = useState<EventType | ''>('')
  const [city, setCity] = useState('')
  const [severity, setSeverity] = useState<Severity | ''>('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const { data, isLoading, isError, error, refetch } = useVerificationQueue({
    filters: {
      status,
      evidence_status: evidenceStatus || undefined,
      event_type: eventType || undefined,
      city: city || undefined,
      severity: severity || undefined,
      start_date: startDate ? `${startDate}T00:00:00` : undefined,
      end_date: endDate ? `${endDate}T23:59:59.999` : undefined,
      limit: PAGE_SIZE,
      offset,
    },
  })

  const columns: TableColumn<AdminQueueEntry>[] = [
    { key: 'category', header: 'Category', render: (e) => EVENT_TYPE_LABEL[e.event_type] ?? e.event_type },
    { key: 'location', header: 'Location', render: (e) => e.location_name },
    { key: 'severity', header: 'Severity', render: (e) => <SeverityBadge severity={e.severity} /> },
    { key: 'time', header: 'Event time', render: (e) => formatDateTime(e.start_time) },
    { key: 'evidence', header: 'Evidence', render: (e) => <EvidenceStatusBadge status={e.evidence_status} /> },
    { key: 'final', header: 'Verification', render: (e) => <FinalStatusBadge status={e.final_verification_status} /> },
    { key: 'reports', header: 'Reports', render: (e) => e.report_count },
    { key: 'updated', header: 'Last updated', render: (e) => formatDateTime(e.updated_at) },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Verification queue</h1>
        <p className="text-sm text-muted">
          Events awaiting review, refreshing automatically. Select an event to inspect its evidence and decide.
        </p>
      </div>

      <FilterBar>
        <FilterField label="Verification status">
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as FinalVerificationStatus | 'ALL')
              setOffset(0)
            }}
          >
            <option value="NEEDS_REVIEW">Needs Review (default)</option>
            <option value="ALL">All statuses</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
          </Select>
        </FilterField>
        <FilterField label="Evidence status">
          <Select
            value={evidenceStatus}
            onChange={(e) => {
              setEvidenceStatus(e.target.value as EvidenceStatus | '')
              setOffset(0)
            }}
          >
            <option value="">All</option>
            {Object.entries(EVIDENCE_STATUS_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="Category">
          <Select
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value as EventType | '')
              setOffset(0)
            }}
          >
            <option value="">All categories</option>
            {Object.entries(EVENT_TYPE_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="Severity">
          <Select
            value={severity}
            onChange={(e) => {
              setSeverity(e.target.value as Severity | '')
              setOffset(0)
            }}
          >
            <option value="">All severities</option>
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="EXTREME">Extreme</option>
          </Select>
        </FilterField>
        <FilterField label="Start date">
          <Input type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setOffset(0) }} />
        </FilterField>
        <FilterField label="End date">
          <Input type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setOffset(0) }} />
        </FilterField>
        <FilterField label="City">
          <Input
            placeholder="e.g. Jabalpur"
            value={city}
            onChange={(e) => {
              setCity(e.target.value)
              setOffset(0)
            }}
          />
        </FilterField>
      </FilterBar>

      <Card>
        <CardBody>
          {isLoading && <LoadingState label="Loading queue" rows={5} />}
          {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}
          {!isLoading && !isError && data && data.items.length === 0 && (
            <EmptyState title="Nothing to review" description="No events match the current filters." />
          )}
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <Table
                columns={columns}
                rows={data.items}
                getRowKey={(e) => e.event_id}
                onRowClick={(e) => navigate(`/admin/events/${e.event_id}`)}
              />
              <Pagination total={data.total} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
