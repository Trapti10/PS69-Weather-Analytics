import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'

export interface StatCardProps {
  label: string
  value: ReactNode
  hint?: string
  icon?: ReactNode
  tone?: 'default' | 'success' | 'warning' | 'danger'
}

const toneText: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'text-foreground',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
}

export function StatCard({ label, value, hint, icon, tone = 'default' }: StatCardProps) {
  return (
    <Card className="flex items-start justify-between gap-3 p-5">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
        <span className={cn('text-2xl font-semibold', toneText[tone])}>{value}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {icon && <div className="text-muted">{icon}</div>}
    </Card>
  )
}
