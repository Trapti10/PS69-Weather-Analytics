import type { ReactNode, SVGProps } from 'react'

export type WeatherGlyphName =
  | 'dashboard'
  | 'temperature'
  | 'rain'
  | 'wind'
  | 'humidity'
  | 'pressure'
  | 'anomaly'
  | 'database'
  | 'fusion'
  | 'shield'
  | 'map'
  | 'research'
  | 'forecast'
  | 'analytics'
  | 'event'
  | 'search'
  | 'cloud'
  | 'check'
  | 'warning'

const PATHS: Record<WeatherGlyphName, ReactNode> = {
  dashboard: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  temperature: <><path d="M10 5a2 2 0 0 1 4 0v8.2a4 4 0 1 1-4 0V5Z" /><path d="M12 16v-7" /></>,
  rain: <><path d="M7 15h10a4 4 0 0 0 .3-8A5.5 5.5 0 0 0 7 9.5 3 3 0 0 0 7 15Z" /><path d="M9 18l-1 2M13 18l-1 2M17 18l-1 2" /></>,
  wind: <><path d="M4 8h11a3 3 0 1 0-3-3" /><path d="M4 12h15a3 3 0 1 1-3 3" /><path d="M4 16h7" /></>,
  humidity: <><path d="M12 3s5 5.4 5 9.2A5 5 0 0 1 7 12.2C7 8.4 12 3 12 3Z" /><path d="M9.5 13.5a2.8 2.8 0 0 0 5 0" /></>,
  pressure: <><circle cx="12" cy="12" r="8" /><path d="m12 12 4-3M12 7v5" /></>,
  anomaly: <><path d="m12 4 8 16H4L12 4Z" /><path d="M12 9v5M12 17h.01" /></>,
  database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" /></>,
  fusion: <><circle cx="8" cy="12" r="3" /><circle cx="16" cy="8" r="3" /><circle cx="16" cy="16" r="3" /><path d="m10.5 10.5 3-1.5M10.5 13.5l3 1.5" /></>,
  shield: <><path d="M12 3 20 6v5c0 5-3.3 8-8 10-4.7-2-8-5-8-10V6l8-3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" /><path d="M9 3v15M15 6v15" /></>,
  research: <><path d="M5 6h10M5 10h8M5 14h6" /><path d="M16 14v5M13.5 16.5h5" /><path d="M4 3h12a2 2 0 0 1 2 2v14H6a2 2 0 0 0-2 2V3Z" /></>,
  forecast: <><path d="M4 18V6M4 18h16" /><path d="m6 15 4-5 3 2 5-7" /></>,
  analytics: <><path d="M4 19V5M4 19h16" /><path d="M7 16v-4M12 16V8M17 16v-7" /><path d="M6 9l4-3 3 2 5-4" /></>,
  event: <><path d="M4 7h16M7 4v6M17 4v6" /><rect x="4" y="6" width="16" height="14" rx="2" /><path d="m9 15 2 2 4-5" /></>,
  search: <><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 5 5" /></>,
  cloud: <><path d="M6 17h11a4 4 0 0 0 .4-8 5.2 5.2 0 0 0-10-1.2A4.3 4.3 0 0 0 6 17Z" /></>,
  check: <><circle cx="12" cy="12" r="8" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  warning: <><path d="m12 4 8 16H4L12 4Z" /><path d="M12 9v5M12 17h.01" /></>,
}

export function WeatherGlyph({ name, className, ...props }: SVGProps<SVGSVGElement> & { name: WeatherGlyphName }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {PATHS[name]}
    </svg>
  )
}
