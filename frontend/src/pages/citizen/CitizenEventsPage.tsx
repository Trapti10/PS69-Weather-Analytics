import { EventsListView } from '@/features/events/EventsListView'

export function CitizenEventsPage() {
  return (
    <EventsListView
      lockedStatus="VERIFIED"
      title="Verified weather events"
      description="Weather events that have been reviewed and confirmed by an administrator."
    />
  )
}
