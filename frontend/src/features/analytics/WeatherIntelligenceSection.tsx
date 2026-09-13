import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { normalizeApiError } from '@/services/api/client'
import { chartColor } from '@/constants/chartColors'
import {
  useAnalyticsOverview,
  useAnomalies,
  useEventDistribution,
  useRainfallAnalytics,
  useSourceComparison,
  useTemperatureAnalytics,
  useVerificationAnalytics,
  useWeatherTrends,
} from '@/features/analytics/useAnalytics'
import {
  ANOMALY_SEVERITY_LABEL,
  ANOMALY_SEVERITY_TONE,
  EVENT_TYPE_LABEL,
  WEATHER_VARIABLE_LABEL,
} from '@/constants/status'

const AXIS_COLOR = 'var(--color-muted)'
const GRID_COLOR = 'var(--color-border)'

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 8,
  color: 'var(--color-foreground)',
}

/**
 * The Analyst/Admin "weather intelligence" panel: every KPI and chart here
 * traces back to a single database-backed /analytics/* endpoint (see
 * backend/api/routes/analytics.py) — none of it is computed from raw rows
 * in the browser, and none of it is hardcoded. Shared by
 * AnalystAnalyticsPage and AdminDashboardPage so the aggregation/rendering
 * logic exists in exactly one place.
 */
export function WeatherIntelligenceSection() {
  const overview = useAnalyticsOverview()
  const trends = useWeatherTrends()
  const temperature = useTemperatureAnalytics()
  const rainfall = useRainfallAnalytics()
  const sourceComparison = useSourceComparison()
  const anomalies = useAnomalies({ latest_limit: 8 })
  const eventDistribution = useEventDistribution()
  const verification = useVerificationAnalytics()

  if (overview.isLoading) {
    return <LoadingState label="Loading weather intelligence" rows={4} />
  }

  if (overview.isError) {
    return (
      <ErrorState message={normalizeApiError(overview.error).message} onRetry={() => overview.refetch()} />
    )
  }

  const kpis = overview.data

  return (
    <div className="flex flex-col gap-6">
      {kpis && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Weather observations" value={kpis.total_weather_observations.toLocaleString()} />
          <StatCard label="Weather events" value={kpis.total_weather_events.toLocaleString()} />
          <StatCard label="Citizen reports" value={kpis.total_reports.toLocaleString()} />
          <StatCard label="Detected anomalies" value={kpis.total_anomalies.toLocaleString()} tone="warning" />
          <StatCard label="Data sources" value={kpis.total_sources} />
          <StatCard label="Verified events" value={kpis.verified_events} tone="success" />
          <StatCard label="Needs review" value={kpis.needs_review} tone="warning" />
          <StatCard
            label="Average temperature"
            value={kpis.average_temperature != null ? `${kpis.average_temperature.toFixed(1)}°C` : '—'}
          />
          <StatCard
            label="Total rainfall"
            value={kpis.total_rainfall != null ? `${kpis.total_rainfall.toLocaleString()} mm` : '—'}
          />
        </div>
      )}

      {kpis && kpis.total_weather_observations === 0 && kpis.total_anomalies === 0 && (
        <EmptyState
          title="No weather intelligence data loaded yet"
          description="Run `python -m backend.db.ingest_analytics_data` to load the collected ERA5/Open-Meteo/anomaly datasets."
        />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* B. Temperature trend */}
        <Card>
          <CardHeader>
            <CardTitle>Temperature trend</CardTitle>
          </CardHeader>
          <CardBody>
            {temperature.isLoading && <LoadingState label="Loading temperature trend" rows={3} />}
            {temperature.isError && (
              <ErrorState message={normalizeApiError(temperature.error).message} onRetry={() => temperature.refetch()} />
            )}
            {temperature.data && temperature.data.trends.length === 0 && (
              <EmptyState title="No temperature data" />
            )}
            {temperature.data && temperature.data.trends.length > 0 && (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={temperature.data.trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={11} minTickGap={30} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} unit="°C" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Line
                    type="monotone"
                    dataKey="average_temperature"
                    name="Avg temp"
                    stroke={chartColor(0)}
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="max_temperature"
                    name="Max temp"
                    stroke={chartColor(3)}
                    strokeWidth={1}
                    dot={false}
                    strokeDasharray="4 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        {/* C. Rainfall trend */}
        <Card>
          <CardHeader>
            <CardTitle>Rainfall trend</CardTitle>
          </CardHeader>
          <CardBody>
            {rainfall.isLoading && <LoadingState label="Loading rainfall trend" rows={3} />}
            {rainfall.isError && (
              <ErrorState message={normalizeApiError(rainfall.error).message} onRetry={() => rainfall.refetch()} />
            )}
            {rainfall.data && rainfall.data.trends.length === 0 && <EmptyState title="No rainfall data" />}
            {rainfall.data && rainfall.data.trends.length > 0 && (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={rainfall.data.trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={11} minTickGap={30} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} unit="mm" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Area
                    type="monotone"
                    dataKey="total_rainfall"
                    name="Rainfall"
                    stroke={chartColor(1)}
                    fill={chartColor(1)}
                    fillOpacity={0.25}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* D. Weather variable trends: humidity / wind speed / pressure */}
        <Card>
          <CardHeader>
            <CardTitle>Humidity &amp; wind trend</CardTitle>
          </CardHeader>
          <CardBody>
            {trends.isLoading && <LoadingState label="Loading trend data" rows={3} />}
            {trends.isError && (
              <ErrorState message={normalizeApiError(trends.error).message} onRetry={() => trends.refetch()} />
            )}
            {trends.data && trends.data.trends.length > 0 && (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trends.data.trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={11} minTickGap={30} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Line
                    type="monotone"
                    dataKey="average_humidity"
                    name={WEATHER_VARIABLE_LABEL.humidity}
                    stroke={chartColor(2)}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="average_wind_speed"
                    name={WEATHER_VARIABLE_LABEL.wind_speed}
                    stroke={chartColor(4)}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        {/* E. Source comparison */}
        <Card>
          <CardHeader>
            <CardTitle>Source comparison</CardTitle>
          </CardHeader>
          <CardBody>
            {sourceComparison.isLoading && <LoadingState label="Loading source comparison" rows={3} />}
            {sourceComparison.isError && (
              <ErrorState
                message={normalizeApiError(sourceComparison.error).message}
                onRetry={() => sourceComparison.refetch()}
              />
            )}
            {sourceComparison.data && sourceComparison.data.sources.length === 0 && (
              <EmptyState title="No source data" />
            )}
            {sourceComparison.data && sourceComparison.data.sources.length > 0 && (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={sourceComparison.data.sources}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="source" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="observation_count" name="Observations" fill={chartColor(0)} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* F. Event distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Event distribution</CardTitle>
          </CardHeader>
          <CardBody>
            {eventDistribution.isLoading && <LoadingState label="Loading event distribution" rows={3} />}
            {eventDistribution.isError && (
              <ErrorState
                message={normalizeApiError(eventDistribution.error).message}
                onRetry={() => eventDistribution.refetch()}
              />
            )}
            {eventDistribution.data && eventDistribution.data.by_event_type.length === 0 && (
              <EmptyState title="No weather events yet" />
            )}
            {eventDistribution.data && eventDistribution.data.by_event_type.length > 0 && (
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={eventDistribution.data.by_event_type}
                    dataKey="count"
                    nameKey="event_type"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {eventDistribution.data.by_event_type.map((entry, index) => (
                      <Cell key={entry.event_type} fill={chartColor(index)} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
            )}
            {eventDistribution.data && eventDistribution.data.by_event_type.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
                {eventDistribution.data.by_event_type.map((entry, index) => (
                  <div key={entry.event_type} className="flex items-center gap-1.5 text-xs text-muted">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: chartColor(index) }} />
                    {EVENT_TYPE_LABEL[entry.event_type] ?? entry.event_type} ({entry.count})
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* H. Verification overview */}
        <Card>
          <CardHeader>
            <CardTitle>Verification overview</CardTitle>
          </CardHeader>
          <CardBody>
            {verification.isLoading && <LoadingState label="Loading verification overview" rows={3} />}
            {verification.isError && (
              <ErrorState
                message={normalizeApiError(verification.error).message}
                onRetry={() => verification.refetch()}
              />
            )}
            {verification.data && verification.data.total_events === 0 && (
              <EmptyState title="No weather events to verify yet" />
            )}
            {verification.data && verification.data.total_events > 0 && (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={[
                    { status: 'Verified', count: verification.data.verified },
                    { status: 'Needs Review', count: verification.data.needs_review },
                    { status: 'Rejected', count: verification.data.rejected },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="status" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    <Cell fill="var(--color-success)" />
                    <Cell fill="var(--color-warning)" />
                    <Cell fill="var(--color-danger)" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      {/* G. Anomaly intelligence */}
      <Card>
        <CardHeader>
          <CardTitle>Anomaly intelligence</CardTitle>
        </CardHeader>
        <CardBody>
          {anomalies.isLoading && <LoadingState label="Loading anomaly intelligence" rows={4} />}
          {anomalies.isError && (
            <ErrorState message={normalizeApiError(anomalies.error).message} onRetry={() => anomalies.refetch()} />
          )}
          {anomalies.data && anomalies.data.total_anomalies === 0 && (
            <EmptyState title="No anomalies detected" description="Nothing flagged in the collected weather data." />
          )}
          {anomalies.data && anomalies.data.total_anomalies > 0 && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={anomalies.data.by_variable_severity}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                    <XAxis
                      dataKey="variable"
                      stroke={AXIS_COLOR}
                      fontSize={11}
                      tickFormatter={(v: string) => WEATHER_VARIABLE_LABEL[v] ?? v}
                    />
                    <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="count" fill={chartColor(5)} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-3 flex flex-wrap gap-2">
                  {anomalies.data.by_severity.map((s) => (
                    <Badge key={s.severity} tone={ANOMALY_SEVERITY_TONE[s.severity]}>
                      {ANOMALY_SEVERITY_LABEL[s.severity]}: {s.count}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Latest anomalies</p>
                <ul className="flex flex-col gap-2">
                  {anomalies.data.latest.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-border px-3 py-2 text-sm"
                    >
                      <div className="flex flex-col">
                        <span className="font-medium text-foreground">
                          {WEATHER_VARIABLE_LABEL[a.variable] ?? a.variable} — {a.source}
                        </span>
                        <span className="text-xs text-muted">
                          {new Date(a.observed_at).toLocaleString()}
                          {(() => {
                            const place =
                              a.location_name ??
                              (a.latitude != null && a.longitude != null
                                ? `${a.latitude.toFixed(2)}, ${a.longitude.toFixed(2)}`
                                : null)
                            return place ? ` · ${place}` : ''
                          })()}
                        </span>
                      </div>
                      <Badge tone={ANOMALY_SEVERITY_TONE[a.severity]}>{ANOMALY_SEVERITY_LABEL[a.severity]}</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
