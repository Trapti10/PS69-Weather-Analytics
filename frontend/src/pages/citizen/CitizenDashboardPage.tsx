import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { EvidenceStatusBadge, FinalStatusBadge } from '@/components/ui/StatusBadge'
import { WeatherGlyph } from '@/components/common/WeatherGlyph'
import { useLocationSearch, useLocationSummary } from '@/features/locations/useLocations'
import { useMyReports } from '@/features/reports/useReports'
import { useAuth } from '@/hooks/useAuth'
import { normalizeApiError } from '@/services/api/client'
import { formatDateTime } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import type { ReportStatusResponse } from '@/types/domain'

export function CitizenDashboardPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState('Jabalpur')
  const [selectedLocation, setSelectedLocation] = useState('Jabalpur, Madhya Pradesh')
  const reports = useMyReports({ limit: 5, offset: 0 })
  const locationSearch = useLocationSearch(search, search.trim().length >= 2)
  const locationSummary = useLocationSummary(selectedLocation)

  const verifiedCount = reports.data?.reports.filter((r: ReportStatusResponse) => r.final_verification_status === 'VERIFIED').length ?? 0

  function submitLocation(e: FormEvent) {
    e.preventDefault()
    const first = locationSearch.data?.locations[0]
    setSelectedLocation(first?.name ?? search.trim())
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="command-hero animate-rise-in">
        <div className="relative z-10 max-w-3xl">
          <DataPill text="PUBLIC WEATHER VIEW" />
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Check weather activity near you</h1>
          <p className="mt-2 text-sm leading-6 text-muted">Search a supported location to see structured weather events, their severity, and verification status.</p>
          <form onSubmit={submitLocation} className="mt-5 flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <WeatherGlyph name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search city or location" className="h-11 w-full rounded-xl border border-border-strong bg-surface pl-10 pr-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted focus:border-primary" />
            </div>
            <Button type="submit" size="lg">Search location</Button>
          </form>
          {locationSearch.data && locationSearch.data.locations.length > 0 && search.trim() && <div className="mt-2 flex flex-wrap gap-2">{locationSearch.data.locations.slice(0, 4).map((location) => <button type="button" key={location.name} onClick={() => { setSelectedLocation(location.name); setSearch(location.name) }} className="filter-chip">{location.name}</button>)}</div>}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Reports submitted" value={reports.data?.total ?? (reports.isLoading ? '—' : 0)} icon={<WeatherGlyph name="research" className="h-4 w-4" />} />
        <StatCard label="Verified reports" value={verifiedCount} tone="success" icon={<WeatherGlyph name="shield" className="h-4 w-4" />} />
        <StatCard label="Events at location" value={locationSummary.data?.events.length ?? (locationSummary.isLoading ? '—' : 0)} icon={<WeatherGlyph name="event" className="h-4 w-4" />} />
        <StatCard label="Historical records" value={locationSummary.data?.observation_count?.toLocaleString() ?? (locationSummary.isLoading ? '—' : 0)} icon={<WeatherGlyph name="database" className="h-4 w-4" />} />
      </div>

      <Card className="animate-rise-in">
        <CardHeader>
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary"><WeatherGlyph name="map" className="h-4 w-4" /></div><div><CardTitle>{locationSummary.data?.location ?? selectedLocation}</CardTitle><p className="mt-1 text-xs text-muted">Location intelligence result</p></div></div>
          {locationSummary.data?.dataset_coverage_start && <span className="text-xs text-muted">Coverage: {new Date(locationSummary.data.dataset_coverage_start).getFullYear()}–{new Date(locationSummary.data.dataset_coverage_end ?? locationSummary.data.dataset_coverage_start).getFullYear()}</span>}
        </CardHeader>
        <CardBody>
          {locationSummary.isLoading && <LoadingState label="Checking location weather activity" rows={4} />}
          {locationSummary.isError && <ErrorState message={normalizeApiError(locationSummary.error).message} onRetry={() => locationSummary.refetch()} />}
          {locationSummary.data && <>
            {locationSummary.data.events.length === 0 ? <EmptyState title="No structured weather events found" description={locationSummary.data.note ?? 'No event records are currently available for this location.'} /> : <div className="grid gap-3 md:grid-cols-2">{locationSummary.data.events.slice(0, 8).map((event) => <div key={event.event_id} className="rounded-xl border border-border bg-surface-muted p-4 transition-transform duration-200 hover:-translate-y-0.5"><div className="flex items-start gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><WeatherGlyph name={event.event_type === 'RAINFALL' ? 'rain' : event.event_type === 'STRONG_WIND' ? 'wind' : event.event_type === 'HEATWAVE' ? 'temperature' : event.event_type === 'THUNDERSTORM' ? 'anomaly' : 'cloud'} className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold text-foreground">{EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}</p><span className="data-pill">{event.severity}</span></div><p className="mt-1 text-xs text-muted">{formatDateTime(event.start_time)}{event.end_time ? ` → ${formatDateTime(event.end_time)}` : ''}</p></div><FinalStatusBadge status={event.final_verification_status} /></div></div>)}</div>}
            {locationSummary.data.note && <p className="mt-4 text-xs leading-5 text-muted">{locationSummary.data.note}</p>}
          </>}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/citizen/report"><Button className="w-full" size="lg"><WeatherGlyph name="event" className="mr-2 h-4 w-4" />Submit a report</Button></Link>
        <Link to="/citizen/events"><Button variant="outline" className="w-full" size="lg">Verified weather events</Button></Link>
        <Link to="/citizen/map"><Button variant="outline" className="w-full" size="lg"><WeatherGlyph name="map" className="mr-2 h-4 w-4" />Open map</Button></Link>
      </div>

      <Card className="animate-rise-in">
        <CardHeader><div><CardTitle>My recent reports</CardTitle><p className="mt-1 text-xs text-muted">Your reporting activity is available here, but it is not the primary weather intelligence view.</p></div></CardHeader>
        <CardBody>
          {reports.isLoading && <LoadingState label="Loading recent reports" rows={3} />}
          {reports.isError && <ErrorState message={normalizeApiError(reports.error).message} onRetry={() => reports.refetch()} />}
          {!reports.isLoading && !reports.isError && reports.data && reports.data.reports.length === 0 && <EmptyState title="No reports yet" description="Submit a weather report to contribute evidence to the platform." />}
          {!reports.isLoading && !reports.isError && reports.data && reports.data.reports.length > 0 && <ul className="flex flex-col divide-y divide-border">{reports.data.reports.map((r) => <li key={r.report_id} className="flex items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-foreground">{r.text}</p><p className="text-xs text-muted">{EVENT_TYPE_LABEL[r.event_type] ?? r.event_type} · {r.city} · {formatDateTime(r.created_at)}</p></div><div className="flex flex-wrap items-center justify-end gap-1">{r.evidence_status && <EvidenceStatusBadge status={r.evidence_status} />}{r.final_verification_status && <FinalStatusBadge status={r.final_verification_status} />}</div></li>)}</ul>}
        </CardBody>
      </Card>
    </div>
  )
}

function DataPill({ text }: { text: string }) {
  return <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">{text}</span>
}
