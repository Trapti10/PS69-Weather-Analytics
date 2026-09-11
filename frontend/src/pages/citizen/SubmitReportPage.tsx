import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { ReportForm } from '@/components/forms/ReportForm'
import { Button } from '@/components/ui/Button'
import { EvidenceStatusBadge } from '@/components/ui/StatusBadge'
import { useSubmitReportMutation } from '@/features/reports/useReports'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime } from '@/utils/format'
import type { ReportSubmissionResponse } from '@/types/domain'

export function SubmitReportPage() {
  const mutation = useSubmitReportMutation()
  const [lastResult, setLastResult] = useState<ReportSubmissionResponse | null>(null)

  const apiError = mutation.isError ? normalizeApiError(mutation.error) : null

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Submit a weather report</h1>
        <p className="text-sm text-muted">
          Report what you're seeing — heavy rain, flooding, strong wind, and more. Your report helps corroborate
          real-time weather events.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardBody>
            <ReportForm
              isSubmitting={mutation.isPending}
              onSubmit={(payload) => {
                mutation.mutate(payload, {
                  onSuccess: (data) => {
                    setLastResult(data)
                  },
                })
              }}
            />
            {apiError && (
              <p role="alert" className="mt-3 text-sm text-danger">
                {apiError.message}
              </p>
            )}
          </CardBody>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Latest submission</CardTitle>
          </CardHeader>
          <CardBody>
            {!lastResult ? (
              <p className="text-sm text-muted">
                Once you submit a report, its status and evidence details will appear here.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-success">Report submitted successfully.</p>
                <dl className="flex flex-col gap-2 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Report ID</dt>
                    <dd className="text-foreground">{lastResult.report_id.slice(0, 8)}…</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Submitted</dt>
                    <dd className="text-foreground">{formatDateTime(lastResult.created_at)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Evidence status</dt>
                    <dd>
                      {lastResult.evidence_status ? (
                        <EvidenceStatusBadge status={lastResult.evidence_status} />
                      ) : (
                        <span className="text-muted">Pending correlation</span>
                      )}
                    </dd>
                  </div>
                </dl>
                <Link to="/citizen/reports">
                  <Button variant="outline" size="sm" className="w-full">
                    View my reports
                  </Button>
                </Link>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
