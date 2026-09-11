import { Link } from 'react-router-dom'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState } from '@/components/ui/AsyncStates'
import { useVerificationQueue } from '@/features/verification/useVerification'
import { normalizeApiError } from '@/services/api/client'

export function AdminDashboardPage() {
  const needsReview = useVerificationQueue({ filters: { status: 'NEEDS_REVIEW', limit: 1 }, poll: true })
  const verified = useVerificationQueue({ filters: { status: 'VERIFIED', limit: 1 }, poll: false })
  const rejected = useVerificationQueue({ filters: { status: 'REJECTED', limit: 1 }, poll: false })

  const isLoading = needsReview.isLoading || verified.isLoading || rejected.isLoading
  const firstError = needsReview.error ?? verified.error ?? rejected.error

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Admin dashboard</h1>
        <p className="text-sm text-muted">Verification workload at a glance, updating automatically.</p>
      </div>

      {isLoading && <LoadingState label="Loading dashboard" rows={2} />}
      {firstError && <ErrorState message={normalizeApiError(firstError).message} />}

      {!isLoading && !firstError && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Needs review" value={needsReview.data?.total ?? 0} tone="warning" />
          <StatCard label="Verified" value={verified.data?.total ?? 0} tone="success" />
          <StatCard label="Rejected" value={rejected.data?.total ?? 0} tone="danger" />
        </div>
      )}

      <Link to="/admin/verification">
        <Button size="lg">Open verification queue</Button>
      </Link>
    </div>
  )
}
