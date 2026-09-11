import type { ReactNode } from 'react'

export interface FilterBarProps {
  children: ReactNode
  onClear?: () => void
}

/** Lays out a row of filter controls responsively; each control is passed as a child. */
export function FilterBar({ children }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-[var(--radius-md)] border border-border bg-surface p-4">
      {children}
    </div>
  )
}

export function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-[140px] flex-col gap-1">
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
    </div>
  )
}
