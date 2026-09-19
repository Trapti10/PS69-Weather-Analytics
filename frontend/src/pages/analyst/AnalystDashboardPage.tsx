import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { WeatherGlyph } from '@/components/common/WeatherGlyph'
import { WeatherIntelligenceSection } from '@/features/analytics/WeatherIntelligenceSection'
import { EventsMapView } from '@/features/events/EventsMapView'

export function AnalystDashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between animate-rise-in">
        <div>
          <p className="eyebrow text-primary">RESEARCHER / ANALYST WORKSPACE</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">Weather Intelligence Command Center</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Explore the collected 2024–2025 Jabalpur weather record, multi-source fusion, corroboration, anomalies, model performance and structured events from the production analytics layer.</p>
        </div>
        <div className="flex gap-2"><Link to="/analyst/data"><Button variant="outline"><WeatherGlyph name="database" className="mr-2 h-4 w-4" />Research Data</Button></Link><Link to="/analyst/events"><Button><WeatherGlyph name="event" className="mr-2 h-4 w-4" />Weather Events</Button></Link></div>
      </div>

      <WeatherIntelligenceSection />

      <EventsMapView
        title="Live geographic intelligence"
        description="Real event coordinates from PostgreSQL/PostGIS. Use the map to connect detected event activity with the structured event and verification layer."
      />
    </div>
  )
}
