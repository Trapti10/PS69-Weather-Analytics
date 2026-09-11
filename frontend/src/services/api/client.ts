import axios, { AxiosError } from 'axios'
import type { ApiErrorBody } from '@/types/domain'
import { getAccessToken, clearAuthStorage } from '@/lib/authStorage'

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** Normalized, UI-friendly error shape produced from any Axios/API failure. */
export interface NormalizedApiError {
  status: number | null
  message: string
  code?: string
  fieldErrors?: { field: string; message: string }[]
}

export function normalizeApiError(error: unknown): NormalizedApiError {
  if (axios.isAxiosError(error)) {
    const err = error as AxiosError<ApiErrorBody>
    const status = err.response?.status ?? null
    const detail = err.response?.data?.detail

    if (!err.response) {
      return { status: null, message: 'Network error — check your connection and try again.' }
    }

    if (status === 401) {
      return { status, message: 'Your session has expired. Please log in again.' }
    }
    if (status === 403) {
      return { status, message: "You don't have permission to do that." }
    }
    if (status === 404) {
      return { status, message: 'The requested resource was not found.' }
    }
    if (status === 422 && Array.isArray(detail)) {
      return {
        status,
        message: 'Please fix the highlighted fields and try again.',
        fieldErrors: detail.map((d) => ({
          field: String(d.loc?.[d.loc.length - 1] ?? 'field'),
          message: d.msg,
        })),
      }
    }
    if (typeof detail === 'string') {
      return { status, message: detail }
    }
    if (status && status >= 500) {
      return { status, message: 'Something went wrong on our end. Please try again shortly.' }
    }
    return { status, message: err.message || 'Something went wrong.' }
  }

  if (error instanceof Error) {
    return { status: null, message: error.message }
  }
  return { status: null, message: 'An unexpected error occurred.' }
}

// Global 401 handling: clear stale auth and let the router redirect to /login.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAuthStorage()
    }
    return Promise.reject(error)
  }
)
