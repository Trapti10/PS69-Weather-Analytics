import { useState } from 'react'
import { Card, CardBody } from '@/components/ui/Card'
import { Table, type TableColumn } from '@/components/ui/Table'
import { Pagination } from '@/components/ui/Pagination'
import { LoadingState, EmptyState, ErrorState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge, SeverityBadge } from '@/components/ui/StatusBadge'
import { FilterBar, FilterField } from '@/components/common/FilterBar'
import { Input, Select } from '@/components/ui/Field'
import { useEvents } from '@/features/events/useEvents'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import type { EventListFilters, EventType, EvidenceStatus, FinalVerificationStatus, Severity, WeatherEvent } from '@/types/domain'

const PAGE_SIZE = 15

export interface EventsListViewProps {
  /** Restricts the view to a fixed status (e.g. citizens only ever see VERIFIED events). */
  lockedStatus?: FinalVerificationStatus
  title: string
  description: string
  onSelectEvent?: (event: WeatherEvent) => void
}

export function EventsListView({ lockedStatus, title, description, onSelectEvent }: EventsListViewProps) {
  const [offset, setOffset] = useState(0)
  const [city, setCity] = useState('')
  const [status, setStatus] = useState<FinalVerificationStatus | ''>(lockedStatus ?? '')
  const [eventType, setEventType] = useState<EventType | ''>('')
  const [evidenceStatus, setEvidenceStatus] = useState<EvidenceStatus | ''>('')
  const [severity, setSeverity] = useState<Severity | ''>('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const filters: EventListFilters = {
    status: lockedStatus ?? (status || undefined),
    event_type: eventType || undefined,
    evidence_status: evidenceStatus || undefined,
    severity: severity || undefined,
    start_date: startDate ? `${startDate}T00:00:00` : undefined,
    end_date: endDate ? `${endDate}T23:59:59.999` : undefined,
    city: city || undefined,
    limit: PAGE_SIZE,
    offset,
  }

  const { data, isLoading, isError, error, refetch } = useEvents(filters)

  const columns: TableColumn<WeatherEvent>[] = [
    { key: 'category', header: 'Category', render: (e) => EVENT_TYPE_LABEL[e.event_type] ?? e.event_type },
    { key: 'location', header: 'Location', render: (e) => e.location_name },
    { key: 'severity', header: 'Severity', render: (e) => <SeverityBadge severity={e.severity} /> },
    { key: 'time', header: 'Event time', render: (e) => formatDateTime(e.start_time) },
    { key: 'evidence', header: 'Evidence', render: (e) => <EvidenceStatusBadge status={e.evidence_status} /> },
    { key: 'final', header: 'Verification', render: (e) => <FinalStatusBadge status={e.final_verification_status} /> },
    { key: 'reports', header: 'Reports', render: (e) => e.report_count },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        <p className="text-sm text-muted">{description}</p>
      </div>

      <FilterBar>
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
        <FilterField label="Event type">
          <Select
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value as EventType | '')
              setOffset(0)
            }}
          >
            <option value="">All types</option>
            {Object.entries(EVENT_TYPE_LABEL).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
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
            <option value="">All evidence</option>
            <option value="SUPPORTED">Supported</option>
            <option value="CONFLICTING">Conflicting</option>
            <option value="UNVERIFIED">Unverified</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient evidence</option>
          </Select>
        </FilterField>
        {!lockedStatus && (
          <FilterField label="Verification status">
            <Select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as FinalVerificationStatus | '')
                setOffset(0)
              }}
            >
              <option value="">All statuses</option>
              <option value="VERIFIED">Verified</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="REJECTED">Rejected</option>
            </Select>
          </FilterField>
        )}
        <FilterField label="Start date">
          <Input type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setOffset(0) }} />
        </FilterField>
        <FilterField label="End date">
          <Input type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setOffset(0) }} />
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
      </FilterBar>

      <Card>
        <CardBody>
          {isLoading && <LoadingState label="Loading events" rows={5} />}
          {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}
          {!isLoading && !isError && data && data.events.length === 0 && (
            <EmptyState title="No events found" description="Try adjusting your filters." />
          )}
          {!isLoading && !isError && data && data.events.length > 0 && (
            <>
              <Table
                columns={columns}
                rows={data.events}
                getRowKey={(e) => e.event_id}
                onRowClick={onSelectEvent}
              />
              <Pagination total={data.total} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
