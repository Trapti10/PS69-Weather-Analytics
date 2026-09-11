/**
 * Mirrors phase5/api/schemas.py's ReportSubmissionRequest field constraints
 * exactly, so the frontend never accepts a value the backend will reject
 * with a 422. If the backend contract changes, update it there first, then
 * mirror the change here.
 *
 *   text: Field(..., min_length=10, max_length=5000)
 *   city: Field(..., max_length=100)
 *   state: Field(None, max_length=100)
 *   latitude: Field(None, ge=-90, le=90)
 *   longitude: Field(None, ge=-180, le=180)
 *   — plus a validator: if latitude is provided, longitude is required.
 */
export const REPORT_TEXT_MIN_LENGTH = 10
export const REPORT_TEXT_MAX_LENGTH = 5000

export const REPORT_CITY_MAX_LENGTH = 100
export const REPORT_STATE_MAX_LENGTH = 100

export const REPORT_LATITUDE_MIN = -90
export const REPORT_LATITUDE_MAX = 90
export const REPORT_LONGITUDE_MIN = -180
export const REPORT_LONGITUDE_MAX = 180
