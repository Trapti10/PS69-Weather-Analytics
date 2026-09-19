import { WeatherIntelligenceSection } from '@/features/analytics/WeatherIntelligenceSection'
import { EventsMapView } from '@/features/events/EventsMapView'

export function AnalystAnalyticsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">National Weather Intelligence</h1>
        <p className="text-sm text-muted">
          Read-only weather intelligence built from the real collected ERA5 and Open-Meteo observations, anomaly detection, model validation, and
          live weather events. Every figure below is aggregated in the database — nothing is
          computed here from raw rows or hardcoded.
        </p>
      </div>

      <WeatherIntelligenceSection />

      {/* I. Geographic intelligence — real WeatherEvent coordinates */}
      <EventsMapView
        title="Geographic intelligence"
        description="Every reported weather event plotted using real coordinates, across every verification status."
      />
    </div>
  )
}
