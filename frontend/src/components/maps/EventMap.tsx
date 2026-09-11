import { useEffect } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import 'leaflet/dist/leaflet.css'
import type { WeatherEvent } from '@/types/domain'
import { EvidenceStatusBadge, FinalStatusBadge } from '@/components/ui/StatusBadge'
import { formatDateTime } from '@/utils/format'
import { EVENT_TYPE_LABEL } from '@/constants/status'

// Vite bundles Leaflet's default marker images incorrectly by default; wire them up explicitly.
const defaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
L.Marker.prototype.options.icon = defaultIcon

export interface EventMapPoint extends Pick<
  WeatherEvent,
  'event_id' | 'event_type' | 'location_name' | 'start_time' | 'evidence_status' | 'final_verification_status'
> {
  latitude: number
  longitude: number
}

export interface EventMapProps {
  points: EventMapPoint[]
  height?: number | string
  onSelect?: (point: EventMapPoint) => void
}

const INDIA_CENTER: [number, number] = [22.9734, 78.6569]
const INDIA_DEFAULT_ZOOM = 5

function FitBounds({ points }: { points: EventMapPoint[] }) {
  const map = useMap()

  useEffect(() => {
    if (points.length === 0) return
    if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], 9)
      return
    }
    const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude] as [number, number]))
    map.fitBounds(bounds, { padding: [32, 32] })
  }, [points, map])

  return null
}

export function EventMap({ points, height = 420, onSelect }: EventMapProps) {
  return (
    <MapContainer
      center={INDIA_CENTER}
      zoom={INDIA_DEFAULT_ZOOM}
      style={{ height, width: '100%' }}
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds points={points} />
      {points.map((point) => (
        <Marker
          key={point.event_id}
          position={[point.latitude, point.longitude]}
          eventHandlers={onSelect ? { click: () => onSelect(point) } : undefined}
        >
          <Popup>
            <div className="flex flex-col gap-1.5 text-xs">
              <p className="text-sm font-semibold text-foreground">
                {EVENT_TYPE_LABEL[point.event_type] ?? point.event_type}
              </p>
              <p className="text-muted">{point.location_name}</p>
              <p className="text-muted">{formatDateTime(point.start_time)}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                <EvidenceStatusBadge status={point.evidence_status} />
                <FinalStatusBadge status={point.final_verification_status} />
              </div>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
