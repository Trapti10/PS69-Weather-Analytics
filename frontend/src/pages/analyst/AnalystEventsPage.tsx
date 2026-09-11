import { EventsListView } from '@/features/events/EventsListView'

export function AnalystEventsPage() {
  return (
    <EventsListView
      title="Weather events"
      description="Read-only view of all reported weather events across every verification status."
    />
  )
}
