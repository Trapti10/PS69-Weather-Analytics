import { Link } from 'react-router-dom'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState } from '@/components/ui/AsyncStates'
import { WeatherGlyph } from '@/components/common/WeatherGlyph'
import { WeatherIntelligenceSection } from '@/features/analytics/WeatherIntelligenceSection'
import { EventsMapView } from '@/features/events/EventsMapView'
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
      <section className="command-hero animate-rise-in">
        <div className="relative z-10 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow text-primary">ADMINISTRATOR / OPERATIONS</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">National Weather Operations Center</h1>
            <p className="mt-2 text-sm leading-6 text-muted">Monitor verification workload alongside the same real weather intelligence pipeline used by Researchers — without mixing evidence status with final administrative decisions.</p>
          </div>
          <Link to="/admin/verification"><Button size="lg"><WeatherGlyph name="shield" className="mr-2 h-4 w-4" />Open verification queue</Button></Link>
        </div>
      </section>

      {isLoading && <LoadingState label="Loading verification operations" rows={2} />}
      {firstError && <ErrorState message={normalizeApiError(firstError).message} />}
      {!isLoading && !firstError && <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><StatCard label="Needs review" value={needsReview.data?.total ?? 0} tone="warning" icon={<WeatherGlyph name="warning" className="h-4 w-4" />} /><StatCard label="Verified" value={verified.data?.total ?? 0} tone="success" icon={<WeatherGlyph name="shield" className="h-4 w-4" />} /><StatCard label="Rejected" value={rejected.data?.total ?? 0} tone="danger" icon={<WeatherGlyph name="event" className="h-4 w-4" />} /></div>}

      <WeatherIntelligenceSection />

      <EventsMapView
        title="Operational event map"
        description="Real PostgreSQL/PostGIS event locations across verification states. Use the verification queue for final decisions."
      />
    </div>
  )
}
