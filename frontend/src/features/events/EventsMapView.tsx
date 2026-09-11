import { Card, CardBody } from '@/components/ui/Card'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { EventMap, type EventMapPoint } from '@/components/maps/EventMap'
import { useEvents } from '@/features/events/useEvents'
import { normalizeApiError } from '@/services/api/client'
import type { FinalVerificationStatus } from '@/types/domain'

export interface EventsMapViewProps {
  lockedStatus?: FinalVerificationStatus
  title: string
  description: string
}

export function EventsMapView({ lockedStatus, title, description }: EventsMapViewProps) {
  const { data, isLoading, isError, error, refetch } = useEvents({
    status: lockedStatus,
    limit: 200,
    offset: 0,
  })

  const points: EventMapPoint[] = (data?.events ?? [])
    .filter((e) => e.latitude !== null && e.latitude !== undefined && e.longitude !== null && e.longitude !== undefined)
    .map((e) => ({
      event_id: e.event_id,
      event_type: e.event_type,
      location_name: e.location_name,
      start_time: e.start_time,
      evidence_status: e.evidence_status,
      final_verification_status: e.final_verification_status,
      latitude: e.latitude as number,
      longitude: e.longitude as number,
    }))

  const totalWithoutCoords = (data?.events.length ?? 0) - points.length

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        <p className="text-sm text-muted">{description}</p>
      </div>

      <Card>
        <CardBody>
          {isLoading && <LoadingState label="Loading map" rows={4} />}
          {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}
          {!isLoading && !isError && points.length === 0 && (
            <EmptyState
              title="No mappable events yet"
              description="Events appear here once they include coordinates from a citizen report."
            />
          )}
          {!isLoading && !isError && points.length > 0 && (
            <>
              <EventMap points={points} height={520} />
              {totalWithoutCoords > 0 && (
                <p className="mt-3 text-xs text-muted">
                  {totalWithoutCoords} additional event{totalWithoutCoords === 1 ? '' : 's'} without coordinates
                  {'  '}(reported without a precise location) are not shown on the map.
                </p>
              )}
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
