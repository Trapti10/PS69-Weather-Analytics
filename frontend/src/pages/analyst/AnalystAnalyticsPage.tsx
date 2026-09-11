import {
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
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { useAnalytics } from '@/features/analytics/useAnalytics'
import { normalizeApiError } from '@/services/api/client'
import { chartColor } from '@/constants/chartColors'

const AXIS_COLOR = 'var(--color-muted)'
const GRID_COLOR = 'var(--color-border)'

export function AnalystAnalyticsPage() {
  const { summary, isLoading, isError, error, refetch } = useAnalytics()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Analytics</h1>
        <p className="text-sm text-muted">
          Derived from live weather event data. No hardcoded figures — every number below reflects the current
          backend state.
        </p>
      </div>

      {isLoading && <LoadingState label="Loading analytics" rows={5} />}
      {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}

      {!isLoading && !isError && summary && summary.totalEvents === 0 && (
        <EmptyState title="No event data yet" description="Analytics will populate once weather events exist." />
      )}

      {!isLoading && !isError && summary && summary.totalEvents > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total events" value={summary.totalEvents} />
            <StatCard label="Verified" value={summary.verifiedCount} tone="success" />
            <StatCard label="Needs review" value={summary.needsReviewCount} tone="warning" />
            <StatCard label="Rejected" value={summary.rejectedCount} tone="danger" />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Events by category</CardTitle>
              </CardHeader>
              <CardBody>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={summary.byCategory}
                      dataKey="count"
                      nameKey="label"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {summary.byCategory.map((entry, index) => (
                        <Cell key={entry.category} fill={chartColor(index)} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 8,
                        color: 'var(--color-foreground)',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
                  {summary.byCategory.map((entry, index) => (
                    <div key={entry.category} className="flex items-center gap-1.5 text-xs text-muted">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: chartColor(index) }}
                      />
                      {entry.label} ({entry.count})
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top locations</CardTitle>
              </CardHeader>
              <CardBody>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={summary.byLocation} layout="vertical" margin={{ left: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
                    <XAxis type="number" stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                    <YAxis type="category" dataKey="location" stroke={AXIS_COLOR} fontSize={12} width={90} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 8,
                        color: 'var(--color-foreground)',
                      }}
                    />
                    <Bar dataKey="count" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Events over time</CardTitle>
            </CardHeader>
            <CardBody>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={summary.byDate}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                  <XAxis dataKey="date" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 8,
                      color: 'var(--color-foreground)',
                    }}
                  />
                  <Line type="monotone" dataKey="count" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
