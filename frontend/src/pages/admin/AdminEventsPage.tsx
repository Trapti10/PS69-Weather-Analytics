import { useNavigate } from 'react-router-dom'
import { EventsListView } from '@/features/events/EventsListView'

/**
 * Admin-only "browse all events" view. Reuses the same read-only
 * EventsListView that Analyst uses (no duplicated table/filter logic) but
 * rows are clickable and route into the existing admin evidence/verification
 * screen (/admin/events/:eventId) instead of being purely informational.
 *
 * This does not duplicate or bypass the verification workflow — clicking a
 * row just navigates to the same AdminEvidenceDetailPage reached from the
 * verification queue, where the real verify/reject/needs-review mutation
 * lives (backend/api/routes/admin.py:verify_event).
 */
export function AdminEventsPage() {
  const navigate = useNavigate()

  return (
    <EventsListView
      title="Weather events"
      description="All reported weather events across every verification status. Select one to inspect its evidence."
      onSelectEvent={(event) => navigate(`/admin/events/${event.event_id}`)}
    />
  )
}
