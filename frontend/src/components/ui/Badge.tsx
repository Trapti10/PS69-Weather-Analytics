import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export type BadgeTone = 'muted' | 'success' | 'warning' | 'danger' | 'info' | 'primary'

const toneClasses: Record<BadgeTone, string> = {
  muted: 'bg-surface-muted text-muted border-border',
  success: 'bg-success-bg text-success border-transparent',
  warning: 'bg-warning-bg text-warning border-transparent',
  danger: 'bg-danger-bg text-danger border-transparent',
  info: 'bg-info-bg text-info border-transparent',
  primary: 'bg-primary/15 text-primary border-transparent',
}

export interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  className?: string
}

export function Badge({ tone = 'muted', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  )
}
