import { EventsMapView } from '@/features/events/EventsMapView'

export function AnalystMapPage() {
  return (
    <EventsMapView
      title="Weather event map"
      description="All reported weather events plotted using real coordinates, across every verification status."
    />
  )
}
