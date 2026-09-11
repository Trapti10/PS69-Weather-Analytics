import { EventsMapView } from '@/features/events/EventsMapView'

export function CitizenMapPage() {
  return (
    <EventsMapView
      lockedStatus="VERIFIED"
      title="Weather event map"
      description="Verified weather events plotted using real reported coordinates."
    />
  )
}
