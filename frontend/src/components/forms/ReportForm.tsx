import { useState, type FormEvent } from 'react'
import { Field, Input, Select, Textarea } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { EVENT_TYPES, type EventType, type ReportSubmissionRequest } from '@/types/domain'
import { EVENT_TYPE_LABEL } from '@/constants/status'
import {
  REPORT_CITY_MAX_LENGTH,
  REPORT_LATITUDE_MAX,
  REPORT_LATITUDE_MIN,
  REPORT_LONGITUDE_MAX,
  REPORT_LONGITUDE_MIN,
  REPORT_STATE_MAX_LENGTH,
  REPORT_TEXT_MAX_LENGTH,
  REPORT_TEXT_MIN_LENGTH,
} from '@/constants/reportValidation'

export interface ReportFormValues {
  text: string
  city: string
  state: string
  latitude: string
  longitude: string
  event_type: EventType | ''
}

const initialValues: ReportFormValues = {
  text: '',
  city: '',
  state: '',
  latitude: '',
  longitude: '',
  event_type: '',
}

export interface ReportFormProps {
  onSubmit: (payload: ReportSubmissionRequest) => void
  isSubmitting?: boolean
}

export function ReportForm({ onSubmit, isSubmitting }: ReportFormProps) {
  const [values, setValues] = useState<ReportFormValues>(initialValues)
  const [errors, setErrors] = useState<Partial<Record<keyof ReportFormValues, string>>>({})

  function update<K extends keyof ReportFormValues>(key: K, value: ReportFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  function validate(): boolean {
    const next: Partial<Record<keyof ReportFormValues, string>> = {}
    const text = values.text.trim()
    const city = values.city.trim()
    const state = values.state.trim()

    if (text.length < REPORT_TEXT_MIN_LENGTH) {
      next.text = `Please describe what you observed (at least ${REPORT_TEXT_MIN_LENGTH} characters).`
    } else if (text.length > REPORT_TEXT_MAX_LENGTH) {
      next.text = `Please keep your description under ${REPORT_TEXT_MAX_LENGTH} characters.`
    }

    if (!city) {
      next.city = 'City is required.'
    } else if (city.length > REPORT_CITY_MAX_LENGTH) {
      next.city = `City must be under ${REPORT_CITY_MAX_LENGTH} characters.`
    }

    if (state.length > REPORT_STATE_MAX_LENGTH) {
      next.state = `State must be under ${REPORT_STATE_MAX_LENGTH} characters.`
    }

    if (!values.event_type) next.event_type = 'Please select an event type.'

    const rawLatitude = values.latitude.trim()
    const rawLongitude = values.longitude.trim()

    if (rawLatitude) {
      const latitude = Number(rawLatitude)
      if (Number.isNaN(latitude)) {
        next.latitude = 'Latitude must be a number.'
      } else if (latitude < REPORT_LATITUDE_MIN || latitude > REPORT_LATITUDE_MAX) {
        next.latitude = `Latitude must be between ${REPORT_LATITUDE_MIN} and ${REPORT_LATITUDE_MAX}.`
      } else if (!rawLongitude) {
        // Matches the backend validator: if latitude is provided, longitude is required.
        next.longitude = 'Longitude is required when latitude is provided.'
      }
    }

    if (rawLongitude && !next.longitude) {
      const longitude = Number(rawLongitude)
      if (Number.isNaN(longitude)) {
        next.longitude = 'Longitude must be a number.'
      } else if (longitude < REPORT_LONGITUDE_MIN || longitude > REPORT_LONGITUDE_MAX) {
        next.longitude = `Longitude must be between ${REPORT_LONGITUDE_MIN} and ${REPORT_LONGITUDE_MAX}.`
      }
    }

    setErrors(next)
    return Object.keys(next).length === 0
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!validate()) return

    onSubmit({
      text: values.text.trim(),
      city: values.city.trim(),
      state: values.state.trim() || null,
      latitude: values.latitude ? Number(values.latitude) : null,
      longitude: values.longitude ? Number(values.longitude) : null,
      event_type: values.event_type,
    })
  }

  function handleUseCurrentLocation() {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition((position) => {
      update('latitude', String(position.coords.latitude))
      update('longitude', String(position.coords.longitude))
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <Field label="What did you observe?" htmlFor="text" required error={errors.text}>
        <Textarea
          id="text"
          required
          minLength={REPORT_TEXT_MIN_LENGTH}
          maxLength={REPORT_TEXT_MAX_LENGTH}
          placeholder="e.g. Heavy rainfall and waterlogging near the main market since 3pm."
          value={values.text}
          onChange={(e) => update('text', e.target.value)}
          error={!!errors.text}
        />
      </Field>

      <Field label="Event type" htmlFor="event_type" required error={errors.event_type}>
        <Select
          id="event_type"
          required
          value={values.event_type}
          onChange={(e) => update('event_type', e.target.value as EventType)}
          error={!!errors.event_type}
        >
          <option value="" disabled>
            Select an event type
          </option>
          {EVENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {EVENT_TYPE_LABEL[type]}
            </option>
          ))}
        </Select>
      </Field>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="City" htmlFor="city" required error={errors.city}>
          <Input
            id="city"
            required
            maxLength={REPORT_CITY_MAX_LENGTH}
            value={values.city}
            onChange={(e) => update('city', e.target.value)}
            error={!!errors.city}
          />
        </Field>
        <Field label="State" htmlFor="state" hint={errors.state ? undefined : 'Optional'} error={errors.state}>
          <Input
            id="state"
            maxLength={REPORT_STATE_MAX_LENGTH}
            value={values.state}
            onChange={(e) => update('state', e.target.value)}
            error={!!errors.state}
          />
        </Field>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Latitude" htmlFor="latitude" hint="Optional — improves map accuracy" error={errors.latitude}>
          <Input
            id="latitude"
            inputMode="decimal"
            placeholder="23.1815"
            value={values.latitude}
            onChange={(e) => update('latitude', e.target.value)}
            error={!!errors.latitude}
          />
        </Field>
        <Field label="Longitude" htmlFor="longitude" hint="Optional — improves map accuracy" error={errors.longitude}>
          <Input
            id="longitude"
            inputMode="decimal"
            placeholder="79.9864"
            value={values.longitude}
            onChange={(e) => update('longitude', e.target.value)}
            error={!!errors.longitude}
          />
        </Field>
      </div>

      <Button type="button" variant="outline" size="sm" className="w-fit" onClick={handleUseCurrentLocation}>
        Use my current location
      </Button>

      <Button type="submit" isLoading={isSubmitting} className="mt-2">
        Submit report
      </Button>
    </form>
  )
}
