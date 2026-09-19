import { useMemo, useState, type ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { WeatherGlyph, type WeatherGlyphName } from '@/components/common/WeatherGlyph'
import { chartColor } from '@/constants/chartColors'
import {
  ANOMALY_SEVERITY_LABEL,
  ANOMALY_SEVERITY_TONE,
  EVENT_TYPE_LABEL,
  WEATHER_VARIABLE_LABEL,
} from '@/constants/status'
import {
  useAnalyticsOverview,
  useAnomalies,
  useCorroborationAnalytics,
  useDataQualityAnalytics,
  useEventDistribution,
  useFusionAnalytics,
  useIntelligenceAnalytics,
  useModelPerformance,
  useRainfallAnalytics,
  useSourceComparison,
  useTemperatureAnalytics,
  useVerificationAnalytics,
  useWeatherTrends,
} from '@/features/analytics/useAnalytics'
import { normalizeApiError } from '@/services/api/client'
import type { AnalyticsFilters } from '@/types/domain'

const AXIS_COLOR = 'var(--color-muted)'
const GRID_COLOR = 'var(--color-border-strong)'
const TOOLTIP_STYLE = {
  backgroundColor: 'var(--color-surface)',
  border: '1px solid var(--color-border-strong)',
  borderRadius: 12,
  color: 'var(--color-foreground)',
  boxShadow: 'var(--shadow-md)',
}

const severityColors: Record<string, string> = {
  LOW: 'var(--color-success)',
  MEDIUM: 'var(--color-warning)',
  HIGH: 'var(--color-warning)',
  CRITICAL: 'var(--color-danger)',
}

function SectionIntro({ eyebrow, title, description, icon }: { eyebrow?: string; title: string; description?: string; icon?: WeatherGlyphName }) {
  return (
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/15">
          <WeatherGlyph name={icon} className="h-5 w-5" />
        </div>
      )}
      <div className="min-w-0">
        {eyebrow && <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary/80">{eyebrow}</p>}
        <h2 className="mt-1 text-base font-semibold text-foreground">{title}</h2>
        {description && <p className="mt-1 text-xs leading-5 text-muted">{description}</p>}
      </div>
    </div>
  )
}

function PanelShell({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <Card className={`animate-rise-in overflow-hidden ${className}`}>{children}</Card>
}

function DataBadge({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-1 text-[10px] font-medium text-muted">{children}</span>
}

export function WeatherIntelligenceSection() {
  const [source, setSource] = useState('')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2025-12-31')
  const filters: AnalyticsFilters = useMemo(
    () => ({
      source: source || undefined,
      start_date: startDate ? `${startDate}T00:00:00` : undefined,
      end_date: endDate ? `${endDate}T23:59:59` : undefined,
    }),
    [source, startDate, endDate]
  )

  const overview = useAnalyticsOverview(filters)
  const dataQuality = useDataQualityAnalytics()
  const trends = useWeatherTrends(filters)
  const temperature = useTemperatureAnalytics(filters)
  const rainfall = useRainfallAnalytics(filters)
  const sourceComparison = useSourceComparison({ start_date: filters.start_date, end_date: filters.end_date })
  const anomalies = useAnomalies({ ...filters, latest_limit: 10 })
  const eventDistribution = useEventDistribution({ start_date: filters.start_date, end_date: filters.end_date })
  const verification = useVerificationAnalytics({ start_date: filters.start_date, end_date: filters.end_date })
  const fusion = useFusionAnalytics()
  const corroboration = useCorroborationAnalytics()
  const intelligence = useIntelligenceAnalytics()
  const models = useModelPerformance()

  const resetFilters = () => {
    setSource('')
    setStartDate('2024-01-01')
    setEndDate('2025-12-31')
  }

  if (overview.isLoading) return <LoadingState label="Loading weather intelligence" rows={6} />
  if (overview.isError) return <ErrorState message={normalizeApiError(overview.error).message} onRetry={() => overview.refetch()} />

  const kpi = overview.data
  const temperatureSeries = temperature.data?.trends ?? []
  const rainfallSeries = rainfall.data?.trends ?? []
  const sourceSeries = sourceComparison.data?.sources ?? []
  const anomalySeries = anomalies.data?.by_month ?? []
  const modelTemperature = models.data?.temperature ?? []
  const modelRainfall = models.data?.rainfall ?? []
  const forecastByHorizon = (models.data?.horizons ?? []).map((horizon) => ({
    horizon: `${horizon}h`,
    temperatureR2: Math.max(...modelTemperature.filter((row) => row.horizon_h === horizon).map((row) => row.r2 ?? Number.NEGATIVE_INFINITY)),
    rainfallAuc: Math.max(...modelRainfall.filter((row) => row.horizon_h === horizon).map((row) => row.roc_auc ?? Number.NEGATIVE_INFINITY)),
  })).map((row) => ({
    ...row,
    temperatureR2: Number.isFinite(row.temperatureR2) ? row.temperatureR2 : null,
    rainfallAuc: Number.isFinite(row.rainfallAuc) ? row.rainfallAuc : null,
  }))

  return (
    <div className="flex flex-col gap-6">
      <section className="command-hero animate-rise-in">
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <DataBadge><span className="inline-block h-1.5 w-1.5 rounded-full bg-success animate-pulse-soft" />Database-backed intelligence</DataBadge>
              <DataBadge>Jabalpur historical focus</DataBadge>
              <DataBadge>2024–2025</DataBadge>
            </div>
            <p className="eyebrow text-primary">NATIONAL WEATHER INTELLIGENCE</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Weather Intelligence Command Center</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
              Collected observations, multi-source fusion, corroboration, forecast models, anomalies and verified weather events — presented from the live PostgreSQL analytics layer.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[470px]">
            <MiniSignal label="Coverage" value={kpi?.observations_date_range_start && kpi.observations_date_range_end ? `${new Date(kpi.observations_date_range_start).getFullYear()}–${new Date(kpi.observations_date_range_end).getFullYear()}` : '—'} icon="event" />
            <MiniSignal label="Sources" value={String(kpi?.total_sources ?? 0)} icon="database" />
            <MiniSignal label="Anomalies" value={(kpi?.total_anomalies ?? 0).toLocaleString()} icon="anomaly" />
            <MiniSignal label="Store" value="PostgreSQL" icon="database" />
          </div>
        </div>
      </section>

      <section className="filter-strip animate-rise-in">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-foreground">Analysis context</p>
            <p className="text-[11px] text-muted">All historical charts use SQL aggregation; filters change the query, not a browser-side raw-data dump.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="filter-control"><span>Source</span><select value={source} onChange={(e) => setSource(e.target.value)}><option value="">All sources</option><option value="ERA5">ERA5</option><option value="Open-Meteo">Open-Meteo</option></select></label>
            <label className="filter-control"><span>From</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
            <label className="filter-control"><span>To</span><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
            <button type="button" onClick={resetFilters} className="filter-reset">Reset</button>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-8">
        <StatCard label="Observation records" value={(kpi?.total_weather_observations ?? 0).toLocaleString()} icon={<WeatherGlyph name="database" className="h-4 w-4" />} />
        <StatCard label="Measurements analysed" value={(kpi?.measurements_analyzed ?? 0).toLocaleString()} icon={<WeatherGlyph name="analytics" className="h-4 w-4" />} />
        <StatCard label="Weather events" value={(kpi?.total_weather_events ?? 0).toLocaleString()} icon={<WeatherGlyph name="event" className="h-4 w-4" />} />
        <StatCard label="Anomalies" value={(kpi?.total_anomalies ?? 0).toLocaleString()} tone="warning" icon={<WeatherGlyph name="anomaly" className="h-4 w-4" />} />
        <StatCard label="Anomaly rate" value={kpi?.anomaly_rate != null ? `${(kpi.anomaly_rate * 100).toFixed(2)}%` : '—'} tone="warning" icon={<WeatherGlyph name="warning" className="h-4 w-4" />} />
        <StatCard label="Sources" value={kpi?.total_sources ?? 0} icon={<WeatherGlyph name="fusion" className="h-4 w-4" />} />
        <StatCard label="Verified" value={kpi?.verified_events ?? 0} tone="success" icon={<WeatherGlyph name="shield" className="h-4 w-4" />} />
        <StatCard label="Avg temperature" value={kpi?.average_temperature != null ? `${kpi.average_temperature.toFixed(1)}°C` : '—'} icon={<WeatherGlyph name="temperature" className="h-4 w-4" />} />
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <PanelShell className="xl:col-span-3">
          <CardHeader><SectionIntro eyebrow="DATA PREPARATION" title="Data quality & processing" description="Persisted preparation checks from the weather-analysis pipeline." icon="analytics" /></CardHeader>
          <CardBody>
            {dataQuality.isLoading ? <LoadingState label="Loading data quality summary" rows={3} /> : dataQuality.isError ? <ErrorState message={normalizeApiError(dataQuality.error).message} onRetry={() => dataQuality.refetch()} /> : dataQuality.data ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <MetricTile label="Measurements" value={dataQuality.data.total_observations_analyzed} icon="analytics" />
                <MetricTile label="Evaluated" value={dataQuality.data.evaluated_observations} icon="check" />
                <MetricTile label="Missing values" value={dataQuality.data.missing_value_count} icon="check" />
                <MetricTile label="Duplicates dropped" value={dataQuality.data.by_source.reduce((sum, item) => sum + item.duplicate_timestamps_dropped, 0)} icon="database" />
              </div>
            ) : <EmptyState title="No data-quality summary" />}
            {dataQuality.data && <div className="mt-3 flex flex-wrap gap-2">
              <DataBadge>{dataQuality.data.variables_analyzed} weather variables evaluated</DataBadge>
              <DataBadge>Insufficient history: {dataQuality.data.insufficient_history_count.toLocaleString()}</DataBadge>
              <DataBadge>Invalid values: {dataQuality.data.invalid_value_count}</DataBadge>
              <DataBadge>Zero variance: {dataQuality.data.zero_variance_count}</DataBadge>
            </div>}
          </CardBody>
        </PanelShell>
        <PanelShell className="xl:col-span-2">
          <CardHeader><SectionIntro eyebrow="SOURCE COVERAGE" title="Prepared source records" description="Input checks retained for each integrated weather source." icon="database" /></CardHeader>
          <CardBody>
            {dataQuality.data?.by_source.length ? <div className="space-y-3">{dataQuality.data.by_source.map((item) => <div key={item.source} className="rounded-xl border border-border bg-surface-muted p-3"><div className="flex items-center justify-between"><span className="text-sm font-medium text-foreground">{item.source}</span><span className="text-xs text-muted">{item.input_records.toLocaleString()} records</span></div><div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-muted"><span>No timestamp: <strong className="text-foreground">{item.records_without_timestamp}</strong></span><span>Duplicates: <strong className="text-foreground">{item.duplicate_timestamps_dropped}</strong></span><span>Invalid rain: <strong className="text-foreground">{item.invalid_rainfall_count}</strong></span></div></div>)}</div> : <EmptyState title="No source preparation data" />}
          </CardBody>
        </PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <PanelShell className="xl:col-span-3">
          <CardHeader><SectionIntro eyebrow="HISTORICAL SIGNAL" title="Temperature trend" description="Daily average and maximum temperature across the selected window." icon="temperature" /></CardHeader>
          <CardBody>
            {temperature.isLoading ? <LoadingState label="Loading temperature trend" rows={3} /> : temperatureSeries.length === 0 ? <EmptyState title="No temperature data" /> : (
              <div className="chart-height"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={temperatureSeries}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={10} minTickGap={36} /><YAxis stroke={AXIS_COLOR} fontSize={11} unit="°C" /><Tooltip contentStyle={TOOLTIP_STYLE} /><Area type="monotone" dataKey="average_temperature" fill={chartColor(0)} fillOpacity={0.08} stroke="none" /><Line type="monotone" dataKey="average_temperature" name="Average" stroke={chartColor(0)} strokeWidth={2.4} dot={false} /><Line type="monotone" dataKey="max_temperature" name="Maximum" stroke={chartColor(3)} strokeWidth={1.5} strokeDasharray="5 5" dot={false} /></ComposedChart></ResponsiveContainer></div>
            )}
            {temperature.data && <div className="mt-3 flex flex-wrap gap-2"><DataBadge>Avg {temperature.data.average_temperature?.toFixed(1) ?? '—'}°C</DataBadge><DataBadge>Max {temperature.data.max_temperature?.toFixed(1) ?? '—'}°C</DataBadge><DataBadge>Min {temperature.data.min_temperature?.toFixed(1) ?? '—'}°C</DataBadge></div>}
          </CardBody>
        </PanelShell>

        <PanelShell className="xl:col-span-2">
          <CardHeader><SectionIntro eyebrow="PRECIPITATION" title="Rainfall signal" description="Daily rainfall totals aggregated from the selected source window." icon="rain" /></CardHeader>
          <CardBody>
            {rainfall.isLoading ? <LoadingState label="Loading rainfall trend" rows={3} /> : rainfallSeries.length === 0 ? <EmptyState title="No rainfall data" /> : (
              <div className="chart-height"><ResponsiveContainer width="100%" height="100%"><AreaChart data={rainfallSeries}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={10} minTickGap={36} /><YAxis stroke={AXIS_COLOR} fontSize={11} unit=" mm" /><Tooltip contentStyle={TOOLTIP_STYLE} /><Area type="monotone" dataKey="total_rainfall" name="Rainfall" stroke={chartColor(1)} fill={chartColor(1)} fillOpacity={0.24} /></AreaChart></ResponsiveContainer></div>
            )}
            {rainfall.data && <div className="mt-3 flex flex-wrap gap-2"><DataBadge>Total {rainfall.data.total_rainfall?.toLocaleString() ?? '—'} mm</DataBadge><DataBadge>Max day {rainfall.data.max_daily_rainfall?.toFixed(1) ?? '—'} mm</DataBadge></div>}
          </CardBody>
        </PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PanelShell><CardHeader><SectionIntro title="Humidity & wind" description="Environmental variables from the same observation store." icon="humidity" /></CardHeader><CardBody><div className="chart-compact"><ResponsiveContainer width="100%" height="100%"><LineChart data={trends.data?.trends ?? []}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={10} minTickGap={30} /><YAxis stroke={AXIS_COLOR} fontSize={10} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Line type="monotone" dataKey="average_humidity" name="Humidity %" stroke={chartColor(2)} dot={false} strokeWidth={2} connectNulls /><Line type="monotone" dataKey="average_wind_speed" name="Wind" stroke={chartColor(4)} dot={false} strokeWidth={2} connectNulls /></LineChart></ResponsiveContainer></div></CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro title="Source comparison" description="Coverage and average temperature by source." icon="fusion" /></CardHeader><CardBody>{sourceSeries.length === 0 ? <EmptyState title="No source comparison" /> : <><div className="chart-compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={sourceSeries}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="source" stroke={AXIS_COLOR} fontSize={10} /><YAxis yAxisId="left" stroke={AXIS_COLOR} fontSize={10} /><YAxis yAxisId="right" orientation="right" stroke={AXIS_COLOR} fontSize={10} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Bar yAxisId="left" dataKey="observation_count" name="Observations" fill={chartColor(1)} radius={[5,5,0,0]} /><Line yAxisId="right" type="monotone" dataKey="average_temperature" name="Avg °C" stroke={chartColor(0)} strokeWidth={2.4} /></BarChart></ResponsiveContainer></div><div className="mt-2 flex flex-wrap gap-2">{sourceSeries.map((item)=><DataBadge key={item.source}>{item.source}: {item.rainfall?.toFixed(1) ?? '—'} mm total</DataBadge>)}</div></>}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro title="Pressure context" description="Average pressure over the selected period." icon="pressure" /></CardHeader><CardBody><div className="flex h-[220px] flex-col justify-between"><div className="rounded-2xl border border-border bg-surface-muted p-4"><div className="flex items-center justify-between"><span className="text-xs text-muted">Mean pressure</span><WeatherGlyph name="pressure" className="h-5 w-5 text-primary" /></div><p className="mt-4 text-3xl font-semibold text-foreground">{(() => { const pressure = (trends.data?.trends ?? []).filter((row) => row.average_pressure != null); return pressure.length ? `${(pressure.reduce((sum, row) => sum + (row.average_pressure ?? 0), 0) / pressure.length).toFixed(1)} hPa` : '—' })()}</p><p className="mt-1 text-xs text-muted">Computed from the aggregated trend response.</p></div><div className="grid grid-cols-2 gap-2"><DataBadge>Wind speed linked</DataBadge><DataBadge>Time-aligned</DataBadge></div></div></CardBody></PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <PanelShell><CardHeader><SectionIntro eyebrow="DATA FUSION" title="ERA5 + Open-Meteo alignment" description="Real multi-source matching and source-agreement results from the stored analytical summary." icon="fusion" /></CardHeader><CardBody>{fusion.isLoading ? <LoadingState label="Loading fusion metrics" rows={3} /> : fusion.isError ? <ErrorState message={normalizeApiError(fusion.error).message} onRetry={() => fusion.refetch()} /> : fusion.data && <div className="space-y-4"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><MetricTile label="ERA5" value={fusion.data.era5_records.toLocaleString()} icon="database" /><MetricTile label="Open-Meteo" value={fusion.data.openmeteo_records.toLocaleString()} icon="cloud" /><MetricTile label="Matched" value={fusion.data.matched_temporal_spatial.toLocaleString()} icon="check" /><MetricTile label="Confidence" value={`${((fusion.data.confidence_mean ?? 0) * 100).toFixed(1)}%`} icon="shield" /></div><div className="chart-compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={fusion.data.agreement_by_variable.map((item) => ({ variable: item.variable, high: Number(item.SOURCE_AGREEMENT_HIGH ?? 0), medium: Number(item.SOURCE_AGREEMENT_MEDIUM ?? 0), disagreement: Number(item.SOURCE_DISAGREEMENT ?? 0) }))}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="variable" stroke={AXIS_COLOR} fontSize={10} tickFormatter={(v) => WEATHER_VARIABLE_LABEL[v] ?? v} /><YAxis stroke={AXIS_COLOR} fontSize={10} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Bar dataKey="high" name="High agreement" stackId="a" fill="var(--color-success)" /><Bar dataKey="medium" name="Medium agreement" stackId="a" fill="var(--color-warning)" /><Bar dataKey="disagreement" name="Disagreement" stackId="a" fill="var(--color-danger)" /></BarChart></ResponsiveContainer></div><div className="rounded-xl border border-info/20 bg-info-bg/40 p-3 text-xs leading-5 text-muted">{fusion.data.scientific_note}</div></div>}</CardBody></PanelShell>

        <PanelShell><CardHeader><SectionIntro eyebrow="CORROBORATION" title="Evidence & corroboration" description="Source-backed evidence status from the existing corroboration summary." icon="shield" /></CardHeader><CardBody>{corroboration.isLoading ? <LoadingState label="Loading corroboration" rows={3} /> : corroboration.isError ? <ErrorState message={normalizeApiError(corroboration.error).message} onRetry={() => corroboration.refetch()} /> : corroboration.data && <div className="space-y-4"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><MetricTile label="Supported" value={corroboration.data.supported} icon="check" /><MetricTile label="Unverified" value={corroboration.data.unverified} icon="event" /><MetricTile label="Conflicting" value={corroboration.data.conflicting} icon="warning" /><MetricTile label="Insufficient" value={corroboration.data.insufficient_evidence} icon="research" /></div><div className="chart-compact"><ResponsiveContainer width="100%" height="100%"><BarChart data={[{status:'Supported', count:corroboration.data.supported},{status:'Unverified',count:corroboration.data.unverified},{status:'Conflicting',count:corroboration.data.conflicting},{status:'Insufficient',count:corroboration.data.insufficient_evidence}]}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="status" stroke={AXIS_COLOR} fontSize={10} /><YAxis stroke={AXIS_COLOR} fontSize={10} allowDecimals={false} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Bar dataKey="count" fill={chartColor(5)} radius={[5,5,0,0]} /></BarChart></ResponsiveContainer></div><div className="rounded-xl border border-warning/20 bg-warning-bg/35 p-3 text-xs leading-5 text-muted">{corroboration.data.honest_note}</div></div>}</CardBody></PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <PanelShell className="xl:col-span-3">
          <CardHeader><SectionIntro eyebrow="DATA PREPARATION" title="Data quality & processing" description="Persisted preparation checks from the weather-analysis pipeline." icon="analytics" /></CardHeader>
          <CardBody>
            {dataQuality.isLoading ? <LoadingState label="Loading data quality summary" rows={3} /> : dataQuality.isError ? <ErrorState message={normalizeApiError(dataQuality.error).message} onRetry={() => dataQuality.refetch()} /> : dataQuality.data ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <MetricTile label="Measurements" value={dataQuality.data.total_observations_analyzed} icon="analytics" />
                <MetricTile label="Evaluated" value={dataQuality.data.evaluated_observations} icon="check" />
                <MetricTile label="Missing values" value={dataQuality.data.missing_value_count} icon="check" />
                <MetricTile label="Duplicates dropped" value={dataQuality.data.by_source.reduce((sum, item) => sum + item.duplicate_timestamps_dropped, 0)} icon="database" />
              </div>
            ) : <EmptyState title="No data-quality summary" />}
            {dataQuality.data && <div className="mt-3 flex flex-wrap gap-2">
              <DataBadge>{dataQuality.data.variables_analyzed} weather variables evaluated</DataBadge>
              <DataBadge>Insufficient history: {dataQuality.data.insufficient_history_count.toLocaleString()}</DataBadge>
              <DataBadge>Invalid values: {dataQuality.data.invalid_value_count}</DataBadge>
              <DataBadge>Zero variance: {dataQuality.data.zero_variance_count}</DataBadge>
            </div>}
          </CardBody>
        </PanelShell>
        <PanelShell className="xl:col-span-2">
          <CardHeader><SectionIntro eyebrow="SOURCE COVERAGE" title="Prepared source records" description="Input checks retained for each integrated weather source." icon="database" /></CardHeader>
          <CardBody>
            {dataQuality.data?.by_source.length ? <div className="space-y-3">{dataQuality.data.by_source.map((item) => <div key={item.source} className="rounded-xl border border-border bg-surface-muted p-3"><div className="flex items-center justify-between"><span className="text-sm font-medium text-foreground">{item.source}</span><span className="text-xs text-muted">{item.input_records.toLocaleString()} records</span></div><div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-muted"><span>No timestamp: <strong className="text-foreground">{item.records_without_timestamp}</strong></span><span>Duplicates: <strong className="text-foreground">{item.duplicate_timestamps_dropped}</strong></span><span>Invalid rain: <strong className="text-foreground">{item.invalid_rainfall_count}</strong></span></div></div>)}</div> : <EmptyState title="No source preparation data" />}
          </CardBody>
        </PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <PanelShell className="xl:col-span-3"><CardHeader><SectionIntro eyebrow="WEATHER INTELLIGENCE" title="Confidence & recent intelligence signals" description="Source agreement, evidence and documented confidence context." icon="research" /></CardHeader><CardBody>{intelligence.isLoading ? <LoadingState label="Loading intelligence" rows={4} /> : intelligence.isError ? <ErrorState message={normalizeApiError(intelligence.error).message} onRetry={() => intelligence.refetch()} /> : intelligence.data && <div className="grid gap-5 lg:grid-cols-2"><div><div className="chart-compact"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={intelligence.data.confidence_bands} dataKey="count" nameKey="band" innerRadius={54} outerRadius={84} paddingAngle={3}><Cell fill={chartColor(0)} /><Cell fill={chartColor(2)} /><Cell fill={chartColor(3)} /></Pie><Tooltip contentStyle={TOOLTIP_STYLE} /></PieChart></ResponsiveContainer></div><div className="mt-2 text-center"><p className="text-2xl font-semibold text-foreground">{((intelligence.data.average_overall_confidence ?? 0) * 100).toFixed(1)}%</p><p className="text-xs text-muted">Average documented confidence</p></div></div><div className="space-y-2">{intelligence.data.latest_signals.map((signal, index) => <div key={`${signal.timestamp}-${index}`} className="signal-row"><div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><WeatherGlyph name={(signal.corroboration === 'SUPPORTED' ? 'check' : signal.source_agreement === 'MATCHED' ? 'fusion' : 'warning')} className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-foreground">{signal.event_category ? EVENT_TYPE_LABEL[signal.event_category] ?? signal.event_category : 'Weather intelligence signal'}</p><p className="text-[11px] text-muted">{signal.timestamp ? new Date(signal.timestamp).toLocaleString() : '—'} · {signal.sources.join(' + ') || 'No source label'}</p></div><span className="text-xs font-semibold text-foreground">{signal.confidence != null ? `${Math.round(signal.confidence * 100)}%` : '—'}</span></div>)}</div></div>}</CardBody></PanelShell>

        <PanelShell className="xl:col-span-2"><CardHeader><SectionIntro eyebrow="ANOMALY MONITOR" title="Anomaly activity" description="Monthly anomaly volume from the database intelligence layer." icon="anomaly" /></CardHeader><CardBody>{anomalies.isLoading ? <LoadingState label="Loading anomalies" rows={3} /> : anomalySeries.length === 0 ? <EmptyState title="No anomaly activity" /> : <div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><AreaChart data={anomalySeries}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="month" stroke={AXIS_COLOR} fontSize={10} minTickGap={22} /><YAxis stroke={AXIS_COLOR} fontSize={10} allowDecimals={false} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Area type="monotone" dataKey="count" name="Anomalies" stroke={chartColor(3)} fill={chartColor(3)} fillOpacity={0.16} /></AreaChart></ResponsiveContainer></div>}</CardBody></PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PanelShell><CardHeader><SectionIntro title="Anomaly severity" icon="warning" /></CardHeader><CardBody>{anomalies.data && anomalies.data.by_severity.length > 0 ? <div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={anomalies.data.by_severity} dataKey="count" nameKey="severity" innerRadius={48} outerRadius={82} paddingAngle={2}>{anomalies.data.by_severity.map((entry) => <Cell key={entry.severity} fill={severityColors[entry.severity] ?? chartColor(0)} />)}</Pie><Tooltip contentStyle={TOOLTIP_STYLE} /></PieChart></ResponsiveContainer></div> : <EmptyState title="No severity data" />}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro title="Variables under watch" icon="temperature" /></CardHeader><CardBody>{anomalies.data && anomalies.data.by_variable.length > 0 ? <div className="space-y-3">{anomalies.data.by_variable.map((entry) => <div key={entry.variable}><div className="mb-1 flex items-center justify-between text-xs"><span className="text-muted">{WEATHER_VARIABLE_LABEL[entry.variable] ?? entry.variable}</span><strong className="text-foreground">{entry.count}</strong></div><div className="h-2 overflow-hidden rounded-full bg-surface-muted"><div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${Math.max(5, (entry.count / Math.max(...anomalies.data.by_variable.map((x) => x.count))) * 100)}%` }} /></div></div>)}</div> : <EmptyState title="No variable data" />}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro title="Anomaly sources" icon="database" /></CardHeader><CardBody>{anomalies.data && anomalies.data.by_source.length > 0 ? <div className="space-y-3">{anomalies.data.by_source.map((entry, index) => <div key={entry.source} className="flex items-center gap-3 rounded-xl border border-border bg-surface-muted p-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><WeatherGlyph name="database" className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-sm font-medium text-foreground">{entry.source}</p><p className="text-[11px] text-muted">flagged anomaly records</p></div><strong className="text-sm text-foreground">{entry.count}</strong><span className="h-2 w-2 rounded-full" style={{ backgroundColor: chartColor(index) }} /></div>)}</div> : <EmptyState title="No anomaly source data" />}</CardBody></PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <PanelShell><CardHeader><SectionIntro eyebrow="FORECAST & MODELS" title="Forecast quality by horizon" description="Saved forecast validation metrics from the deployed analytics layer." icon="forecast" /></CardHeader><CardBody>{models.isLoading ? <LoadingState label="Loading forecast metrics" rows={3} /> : models.data && models.data.horizons.length > 0 ? <><div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><LineChart data={forecastByHorizon}><CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} /><XAxis dataKey="horizon" stroke={AXIS_COLOR} fontSize={10} /><YAxis stroke={AXIS_COLOR} fontSize={10} domain={[0.4,1]} /><Tooltip contentStyle={TOOLTIP_STYLE} /><Line type="monotone" dataKey="temperatureR2" name="Temperature R²" stroke={chartColor(0)} strokeWidth={2.4} dot={{ r: 3 }} /><Line type="monotone" dataKey="rainfallAuc" name="Rainfall ROC-AUC" stroke={chartColor(1)} strokeWidth={2.4} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div><div className="mt-3 grid grid-cols-2 gap-2"><DataBadge>{models.data.headline.models_saved ?? models.data.temperature.length + models.data.rainfall.length} saved model rows</DataBadge><DataBadge>{models.data.horizons.length} forecast horizons</DataBadge></div></> : <EmptyState title="No model metrics" />}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro eyebrow="MODEL MATRIX" title="Forecast model comparison" description="Saved validation metrics across models and forecast horizons." icon="forecast" /></CardHeader><CardBody>{models.data && models.data.temperature.length > 0 ? <div className="overflow-x-auto"><table className="min-w-full text-left text-[11px]"><thead><tr className="border-b border-border text-muted"><th className="px-2 py-2">Target</th><th className="px-2 py-2">Horizon</th><th className="px-2 py-2">Model</th><th className="px-2 py-2">MAE</th><th className="px-2 py-2">RMSE</th><th className="px-2 py-2">R² / AUC</th></tr></thead><tbody>{[...models.data.temperature.slice(0, 6), ...models.data.rainfall.filter((row) => row.horizon_h === 1 || row.horizon_h === 24).slice(0, 2)].map((row, index) => <tr key={`${row.target}-${row.model}-${row.horizon_h}-${index}`} className="border-b border-border/60"><td className="px-2 py-2 text-foreground">{row.target}</td><td className="px-2 py-2 text-muted">{row.horizon_h}h</td><td className="px-2 py-2 font-medium text-foreground">{row.model}</td><td className="px-2 py-2 text-muted">{row.mae != null ? row.mae.toFixed(3) : '—'}</td><td className="px-2 py-2 text-muted">{row.rmse != null ? row.rmse.toFixed(3) : '—'}</td><td className="px-2 py-2 text-foreground">{row.r2 != null ? `R² ${row.r2.toFixed(3)}` : row.roc_auc != null ? `AUC ${row.roc_auc.toFixed(3)}` : '—'}</td></tr>)}</tbody></table></div> : <EmptyState title="No model comparison data" />}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro eyebrow="EVENT INTELLIGENCE" title="Weather event distribution" description="Structured events generated by the report/event pipeline, separate from raw scientific observations." icon="event" /></CardHeader><CardBody>{eventDistribution.data && eventDistribution.data.by_event_type.length > 0 ? <><div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={eventDistribution.data.by_event_type} dataKey="count" nameKey="event_type" innerRadius={48} outerRadius={82} paddingAngle={2}>{eventDistribution.data.by_event_type.map((entry,index)=><Cell key={entry.event_type} fill={chartColor(index)} />)}</Pie><Tooltip contentStyle={TOOLTIP_STYLE} /></PieChart></ResponsiveContainer></div><div className="mt-3 flex flex-wrap gap-2">{eventDistribution.data.by_event_type.map((entry,index)=><DataBadge key={entry.event_type}><span className="h-2 w-2 rounded-full" style={{backgroundColor:chartColor(index)}} />{EVENT_TYPE_LABEL[entry.event_type] ?? entry.event_type} · {entry.count}</DataBadge>)}</div></> : <EmptyState title="No structured events in selected window" />}</CardBody></PanelShell>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PanelShell className="lg:col-span-2"><CardHeader><SectionIntro eyebrow="LATEST SIGNALS" title="Latest detected anomalies" description="The most recent flagged records with real source, variable, location and method metadata." icon="anomaly" /></CardHeader><CardBody>{anomalies.data && anomalies.data.latest.length > 0 ? <div className="overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr className="border-b border-border text-muted"><th className="px-2 py-2 font-medium">When</th><th className="px-2 py-2 font-medium">Variable</th><th className="px-2 py-2 font-medium">Source</th><th className="px-2 py-2 font-medium">Observed</th><th className="px-2 py-2 font-medium">Baseline</th><th className="px-2 py-2 font-medium">Severity</th></tr></thead><tbody>{anomalies.data.latest.map((row) => <tr key={row.id} className="border-b border-border/70 transition-colors hover:bg-surface-hover"><td className="whitespace-nowrap px-2 py-2 text-muted">{new Date(row.observed_at).toLocaleString()}</td><td className="px-2 py-2 text-foreground">{WEATHER_VARIABLE_LABEL[row.variable] ?? row.variable}</td><td className="px-2 py-2 text-foreground">{row.source}</td><td className="px-2 py-2 font-medium text-foreground">{row.observed_value?.toFixed(2) ?? '—'}</td><td className="px-2 py-2 text-muted">{row.baseline_value?.toFixed(2) ?? '—'}</td><td className="px-2 py-2"><Badge tone={ANOMALY_SEVERITY_TONE[row.severity]}>{ANOMALY_SEVERITY_LABEL[row.severity]}</Badge></td></tr>)}</tbody></table></div> : <EmptyState title="No anomalies in selected filters" />}</CardBody></PanelShell>
        <PanelShell><CardHeader><SectionIntro eyebrow="VERIFICATION" title="Final event verification" description="Admin workflow status stays separate from system evidence status." icon="shield" /></CardHeader><CardBody>{verification.data && verification.data.total_events > 0 ? <div className="space-y-3"><VerificationBar label="Verified" value={verification.data.verified} total={verification.data.total_events} tone="success" /><VerificationBar label="Needs review" value={verification.data.needs_review} total={verification.data.total_events} tone="warning" /><VerificationBar label="Rejected" value={verification.data.rejected} total={verification.data.total_events} tone="danger" /><div className="mt-4 rounded-xl border border-border bg-surface-muted p-3 text-xs text-muted">Final verification is an administrative decision. It is not the same field as evidence status or corroboration.</div></div> : <EmptyState title="No events to verify" />}</CardBody></PanelShell>
      </section>
    </div>
  )
}

function MiniSignal({ label, value, icon }: { label: string; value: string; icon: WeatherGlyphName }) {
  return <div className="rounded-xl border border-border bg-surface/70 p-3 backdrop-blur"><div className="flex items-center gap-2 text-muted"><WeatherGlyph name={icon} className="h-3.5 w-3.5" /><span className="text-[10px] uppercase tracking-wide">{label}</span></div><p className="mt-2 text-sm font-semibold text-foreground">{value}</p></div>
}

function MetricTile({ label, value, icon }: { label: string; value: string | number; icon: WeatherGlyphName }) {
  return <div className="rounded-xl border border-border bg-surface-muted/70 p-3"><div className="flex items-center justify-between"><span className="text-[10px] uppercase tracking-wide text-muted">{label}</span><WeatherGlyph name={icon} className="h-4 w-4 text-primary" /></div><p className="mt-2 text-lg font-semibold text-foreground">{typeof value === 'number' ? value.toLocaleString() : value}</p></div>
}

function VerificationBar({ label, value, total, tone }: { label: string; value: number; total: number; tone: 'success' | 'warning' | 'danger' }) {
  const pct = total ? Math.round((value / total) * 100) : 0
  const toneClass = tone === 'success' ? 'bg-success' : tone === 'warning' ? 'bg-warning' : 'bg-danger'
  return <div><div className="mb-1 flex items-center justify-between text-xs"><span className="text-muted">{label}</span><strong className="text-foreground">{value} · {pct}%</strong></div><div className="h-2 overflow-hidden rounded-full bg-surface-muted"><div className={`h-full rounded-full ${toneClass} transition-all duration-700`} style={{ width: `${pct}%` }} /></div></div>
}
