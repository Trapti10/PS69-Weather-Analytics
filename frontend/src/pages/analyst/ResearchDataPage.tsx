import { useMemo, useState } from 'react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/AsyncStates'
import { WeatherGlyph, type WeatherGlyphName } from '@/components/common/WeatherGlyph'
import { useResearchArtifactDownload, useResearchArtifactPreview, useResearchArtifacts } from '@/features/research/useResearchData'
import { normalizeApiError } from '@/services/api/client'
import type { ResearchArtifact } from '@/types/domain'

const CATEGORY_ICONS: Record<string, WeatherGlyphName> = {
  'SOURCE DATA': 'cloud',
  'PROCESSED DATA': 'research',
  'DATA FUSION': 'fusion',
  'WEATHER INTELLIGENCE': 'research',
  CORROBORATION: 'shield',
  ANOMALIES: 'anomaly',
  'FORECAST & MODELS': 'forecast',
  REPORTS: 'event',
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ResearchDataPage() {
  const { data, isLoading, isError, error, refetch } = useResearchArtifacts()
  const [category, setCategory] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const preview = useResearchArtifactPreview(selectedId)
  const download = useResearchArtifactDownload()

  const groups = useMemo(() => {
    const artifacts = data?.artifacts ?? []
    return category === 'ALL' ? artifacts : artifacts.filter((item) => item.category === category)
  }, [category, data?.artifacts])

  const categories = useMemo(() => Array.from(new Set(data?.artifacts.map((item) => item.category) ?? [])), [data?.artifacts])

  async function handleDownload(artifact: ResearchArtifact) {
    const blob = await download.mutateAsync(artifact.artifact_id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = artifact.name.replaceAll(' ', '_') + `.${artifact.format.toLowerCase()}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="command-hero animate-rise-in">
        <div className="relative z-10 max-w-3xl">
          <div className="flex items-center gap-2"><span className="eyebrow text-primary">RESEARCH DATA CENTER</span><span className="data-pulse" /></div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Research Data & Artifacts</h1>
          <p className="mt-2 text-sm leading-6 text-muted">Access the real datasets, fusion outputs, intelligence records, anomaly analysis and forecast metrics used by this platform.</p>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        <button type="button" className={category === 'ALL' ? 'filter-chip active' : 'filter-chip'} onClick={() => setCategory('ALL')}>All artifacts</button>
        {categories.map((item) => <button type="button" key={item} className={category === item ? 'filter-chip active' : 'filter-chip'} onClick={() => setCategory(item)}>{item}</button>)}
      </div>

      {isLoading && <LoadingState label="Loading research data catalog" rows={5} />}
      {isError && <ErrorState message={normalizeApiError(error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && groups.length === 0 && <EmptyState title="No research artifacts" />}

      {!isLoading && !isError && groups.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {groups.map((artifact, index) => (
            <Card key={artifact.artifact_id} className="artifact-card animate-rise-in" style={{ animationDelay: `${Math.min(index * 35, 260)}ms` }}>
              <CardBody className="flex h-full flex-col gap-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><WeatherGlyph name={CATEGORY_ICONS[artifact.category] ?? 'research'} className="h-5 w-5" /></div>
                  <div className="min-w-0 flex-1"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary/80">{artifact.category}</p><h2 className="mt-1 text-sm font-semibold text-foreground">{artifact.name}</h2><p className="mt-1 text-xs leading-5 text-muted">{artifact.description}</p></div>
                </div>
                <div className="flex flex-wrap gap-2"><span className="data-pill">{artifact.format}</span><span className="data-pill">{formatBytes(artifact.size_bytes)}</span>{artifact.row_count != null && <span className="data-pill">{artifact.row_count.toLocaleString()} rows</span>}</div>
                <div className="mt-auto flex gap-2 pt-1"><Button size="sm" variant="outline" onClick={() => setSelectedId(artifact.artifact_id)}>Preview</Button><Button size="sm" onClick={() => handleDownload(artifact)} isLoading={download.isPending && download.variables === artifact.artifact_id}>Download</Button></div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {selectedId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" onClick={() => setSelectedId(null)}><div className="max-h-[85vh] w-full max-w-6xl overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--shadow-lg)]" onClick={(e) => e.stopPropagation()}><div className="flex items-center justify-between border-b border-border px-5 py-4"><div><p className="text-[10px] uppercase tracking-wider text-primary">Artifact preview</p><h2 className="text-sm font-semibold text-foreground">{preview.data?.artifact.name ?? 'Loading…'}</h2></div><button type="button" className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-surface-hover hover:text-foreground" onClick={() => setSelectedId(null)}>Close</button></div><div className="max-h-[70vh] overflow-auto p-5">{preview.isLoading && <LoadingState label="Loading preview" rows={4} />}{preview.isError && <ErrorState message={normalizeApiError(preview.error).message} onRetry={() => preview.refetch()} />}{preview.data && preview.data.columns.length > 0 && <div className="overflow-auto"><table className="min-w-full text-left text-xs"><thead className="sticky top-0 bg-surface"><tr className="border-b border-border">{preview.data.columns.map((column) => <th key={column} className="px-3 py-2 font-semibold text-muted">{column}</th>)}</tr></thead><tbody>{preview.data.rows.map((row, index) => <tr key={index} className="border-b border-border/60 align-top"><td colSpan={0} className="hidden" />{preview.data.columns.map((column) => <td key={column} className="max-w-[320px] px-3 py-2 text-foreground"><div className="max-h-20 overflow-hidden whitespace-pre-wrap">{typeof row[column] === 'object' ? JSON.stringify(row[column]) : String(row[column] ?? '—')}</div></td>)}</tr>)}</tbody></table></div>}</div></div></div>}
    </div>
  )
}
