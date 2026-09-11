/**
 * Centralized chart color palette. These reference the same CSS custom
 * properties defined in styles/index.css (--color-chart-1..8), which are
 * themed per dark/light mode alongside every other design token — charts
 * must never hardcode their own independent hex palette.
 */
export const CHART_COLORS: string[] = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-6)',
  'var(--color-chart-7)',
  'var(--color-chart-8)',
]

export function chartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length]
}
