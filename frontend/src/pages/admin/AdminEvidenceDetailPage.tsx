import { useState, type ReactNode } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Field, Select, Textarea } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { LoadingState, ErrorState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge, SeverityBadge } from '@/components/ui/StatusBadge'
import { useEventEvidence, useVerifyEventMutation } from '@/features/verification/useVerification'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime, formatPercent, truncate } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import type { EvidenceReportItem, FinalVerificationStatus } from '@/types/domain'

const ACTIONS: { value: FinalVerificationStatus; label: string; requiresNotes: boolean }[] = [
  { value: 'VERIFIED', label: 'Verify', requiresNotes: false },
  { value: 'NEEDS_REVIEW', label: 'Keep needs review', requiresNotes: true },
  { value: 'REJECTED', label: 'Reject', requiresNotes: true },
]

export function AdminEvidenceDetailPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const navigate = useNavigate()
  const { data, isLoading, isError, error, refetch } = useEventEvidence(eventId)
  const mutation = useVerifyEventMutation(eventId)

  const [action, setAction] = useState<FinalVerificationStatus>('VERIFIED')
  const [notes, setNotes] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [notesError, setNotesError] = useState<string | null>(null)

  if (isLoading) return <LoadingState label="Loading evidence" rows={6} />
  if (isError) return <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  const { event, reports } = data
  const selectedAction = ACTIONS.find((a) => a.value === action)

  function handleConfirmSubmit() {
    if (selectedAction?.requiresNotes && notes.trim().length === 0) {
      setNotesError('Please provide a reason for this decision.')
      return
    }
    setNotesError(null)
    mutation.mutate(
      { action, notes: notes.trim() || null },
      {
        onSuccess: () => setConfirmOpen(false),
      }
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Link to="/admin/verification" className="text-xs text-muted hover:text-foreground">
            ← Back to queue
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-foreground">
            {EVENT_TYPE_LABEL[event.event_type] ?? event.event_type} — {event.location_name}
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Event summary</CardTitle>
            </CardHeader>
            <CardBody>
              <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <Detail label="Severity">
                  <SeverityBadge severity={event.severity} />
                </Detail>
                <Detail label="Evidence status">
                  <EvidenceStatusBadge status={event.evidence_status} />
                </Detail>
                <Detail label="Current verification">
                  <FinalStatusBadge status={event.final_verification_status} />
                </Detail>
                <Detail label="Confidence">{formatPercent(event.evidence_support_score)}</Detail>
                <Detail label="Report count">{event.report_count}</Detail>
                <Detail label="Unique sources">{event.unique_sources}</Detail>
                <Detail label="Start time">{formatDateTime(event.start_time)}</Detail>
                <Detail label="End time">{formatDateTime(event.end_time)}</Detail>
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Supporting reports ({reports.length})</CardTitle>
            </CardHeader>
            <CardBody>
              {reports.length === 0 ? (
                <p className="text-sm text-muted">No individual reports are linked to this event.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-border">
                  {reports.map((r) => (
                    <ReportEvidenceRow key={r.report_id} report={r} />
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Verification decision</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-4">
              <Field label="Decision" htmlFor="action">
                <Select id="action" value={action} onChange={(e) => setAction(e.target.value as FinalVerificationStatus)}>
                  {ACTIONS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Notes"
                htmlFor="notes"
                required={selectedAction?.requiresNotes}
                hint={selectedAction?.requiresNotes ? undefined : 'Optional'}
                error={notesError ?? undefined}
              >
                <Textarea
                  id="notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Reasoning for this decision…"
                  error={!!notesError}
                />
              </Field>

              {mutation.isError && (
                <p role="alert" className="text-sm text-danger">
                  {normalizeApiError(mutation.error).message}
                </p>
              )}

              <Button onClick={() => setConfirmOpen(true)} isLoading={mutation.isPending}>
                Submit decision
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm verification decision"
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={action === 'REJECTED' ? 'danger' : 'primary'}
              onClick={handleConfirmSubmit}
              isLoading={mutation.isPending}
            >
              Confirm {selectedAction?.label}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          You're about to mark this event as{' '}
          <span className="font-medium text-foreground">{selectedAction?.label}</span>. This will update its final
          verification status immediately and cannot be undone from this screen.
        </p>
      </Modal>

      {mutation.isSuccess && (
        <SuccessBanner onDismiss={() => navigate('/admin/verification')} />
      )}
    </div>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  )
}

function ReportEvidenceRow({ report }: { report: EvidenceReportItem }) {
  return (
    <li className="flex flex-col gap-1.5 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-foreground">{truncate(report.text ?? '—', 90)}</p>
        <div className="flex gap-1.5">
          {report.is_duplicate && <Badge tone="muted">Duplicate</Badge>}
          {report.is_suspicious && <Badge tone="danger">Suspicious</Badge>}
        </div>
      </div>
      <p className="text-xs text-muted">
        {report.source_type ?? 'Unknown source'} · {[report.city, report.state].filter(Boolean).join(', ')} ·{' '}
        {formatDateTime(report.report_timestamp)}
      </p>
      <p className="text-xs text-muted">
        Classification: {report.predicted_event_category ?? '—'} (
        {formatPercent(report.event_classification_confidence)}) · Reliability:{' '}
        {formatPercent(report.source_reliability)} · Risk: {report.risk_label ?? '—'}
      </p>
    </li>
  )
}

function SuccessBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-success/30 bg-success-bg px-4 py-3">
      <p className="text-sm text-success">Decision saved successfully.</p>
      <Button variant="outline" size="sm" onClick={onDismiss}>
        Back to queue
      </Button>
    </div>
  )
}
