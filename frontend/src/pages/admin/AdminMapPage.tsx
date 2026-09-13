import { EventsMapView } from '@/features/events/EventsMapView'

/**
 * Admin-only event map. Reuses the same EventsMapView/EventMap components as
 * Analyst and Citizen (no duplicated Leaflet wiring) — Admin sees every
 * verification status, same visibility rule already enforced server-side by
 * GET /events for ANALYST/ADMIN roles.
 */
export function AdminMapPage() {
  return (
    <EventsMapView
      title="Weather event map"
      description="All reported weather events plotted using real coordinates, across every verification status."
    />
  )
}
