# Phase 5 API Documentation

## Overview

Phase 5 MVP API provides endpoints for:
- User authentication (register, login, token refresh)
- Citizen report submission (synchronous processing)
- Event querying (role-aware)
- Report status tracking

All endpoints use JWT authentication except `/auth` endpoints which handle registration/login.

## Authentication

### POST /auth/register
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password_123",
  "role": "CITIZEN"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user_id": "uuid",
  "role": "CITIZEN",
  "expires_in": 86400
}
```

### POST /auth/login
Login with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password_123"
}
```

**Response (200):** Same as register

### POST /auth/refresh
Refresh access token using refresh token.

**Request:**
```
POST /auth/refresh?refresh_token=<refresh_token_string>
```

**Response (200):** Same as login

## Citizens Reports

### POST /reports
Submit a new weather report. **SYNCHRONOUS MVP PROCESSING**.

Processing flow (all within this endpoint):
1. Validate input
2. Normalize report (Phase 3A)
3. Classify event (Phase 3B)
4. Correlate with existing reports (Phase 5)
5. Score evidence (Phase 3C) - uses real ERA5/Open-Meteo data
6. Assign Evidence Status
7. Create/update WeatherEvent
8. Store in PostgreSQL
9. Return response

**Latency:** ~1-3 seconds

**Request:**
```json
{
  "text": "Heavy rainfall and waterlogging near MG Road",
  "city": "Jabalpur",
  "state": "Madhya Pradesh",
  "latitude": 23.1815,
  "longitude": 79.9864,
  "event_type": "RAINFALL",
  "image_url": "https://example.com/photo.jpg",
  "video_url": null
}
```

**Response (200):**
```json
{
  "report_id": "uuid",
  "event_id": "uuid",
  "evidence_status": "SUPPORTED",
  "evidence_support_score": 0.75,
  "verification_status": "UNVERIFIED",
  "created_at": "2026-09-04T10:30:00"
}
```

**Evidence Status Values:**
- `SUPPORTED` - available weather evidence consistent with report
- `CONFLICTING` - available weather evidence contradicts report
- `UNVERIFIED` - evidence inconclusive
- `INSUFFICIENT_EVIDENCE` - no usable evidence available

**Error (422):** Validation error
- Text too short (min 10 chars)
- Invalid coordinates
- Missing required fields

**Error (401):** Not authenticated
**Error (500):** Server error during processing

### GET /reports/{report_id}/status
Get status of a report.

**Authorization:** Any authenticated user (citizens see own reports only)

**Response (200):**
```json
{
  "report_id": "uuid",
  "source_type": "CITIZEN_REPORT",
  "text": "...",
  "city": "Jabalpur",
  "state": "Madhya Pradesh",
  "event_type": "RAINFALL",
  "verification_status": "UNVERIFIED",
  "event_id": "uuid",
  "created_at": "2026-09-04T10:30:00",
  "updated_at": "2026-09-04T10:30:00"
}
```

**Error (403):** Access denied (citizen viewing other user's report)
**Error (404):** Report not found

### GET /reports/me
List only the authenticated user's own submitted reports with pagination.

**Authorization:** Any authenticated user; results are always scoped to the caller.

**Query Parameters:**
- `limit` (optional, default=20, max=100)
- `offset` (optional, default=0)

The response includes report-level `verification_status`, system `evidence_status`, and linked event `final_verification_status` separately.

## Events

### GET /events
List weather events with role-based filtering.

**Authorization:** Any authenticated user

**Query Parameters:**
- `status` (optional): `VERIFIED`, `NEEDS_REVIEW`, `REJECTED`
- `evidence_status` (optional): `SUPPORTED`, `CONFLICTING`, `UNVERIFIED`, `INSUFFICIENT_EVIDENCE`
- `event_type` (optional): event category such as `RAINFALL`, `FLOODING`
- `severity` (optional): `LOW`, `MEDIUM`, `HIGH`, `EXTREME`
- `city` (optional): Location name filter
- `start_date` / `end_date` (optional): `start_time` range
- `limit` (optional, default=50, max=500): Pagination limit
- `offset` (optional, default=0): Pagination offset

**Role-Based Visibility:**
- **CITIZEN**: Only sees VERIFIED events
- **ANALYST/ADMIN**: Sees all events

**Response (200):**
```json
{
  "events": [
    {
      "event_id": "uuid",
      "event_type": "RAINFALL",
      "location_name": "Jabalpur",
      "severity": "HIGH",
      "evidence_status": "SUPPORTED",
      "evidence_support_score": 0.75,
      "final_verification_status": "VERIFIED",
      "report_count": 3,
      "unique_sources": 2,
      "start_time": "2026-09-04T10:00:00",
      "created_at": "2026-09-04T10:00:00"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**Examples:**

Get all verified rainfall events in Jabalpur:
```
GET /events?event_type=RAINFALL&city=Jabalpur&status=VERIFIED
```

Get all high-severity events (analyst):
```
GET /events?severity=HIGH
```

### GET /events/{event_id}
Get detailed information about a specific event.

**Authorization:** CITIZEN (only VERIFIED), ANALYST/ADMIN (any status)

**Response (200):**
```json
{
  "event_id": "uuid",
  "event_type": "RAINFALL",
  "location_name": "Jabalpur",
  "severity": "HIGH",
  "start_time": "2026-09-04T10:00:00",
  "end_time": "2026-09-04T12:00:00",
  "evidence_status": "SUPPORTED",
  "evidence_support_score": 0.75,
  "evidence_detail": {
    "source_verdicts": [
      {
        "source_name": "ERA5",
        "verdict": "SUPPORTING_EVIDENCE",
        "value": 15.2,
        "unit": "mm"
      }
    ]
  },
  "final_verification_status": "VERIFIED",
  "report_count": 3,
  "unique_sources": 2,
  "member_report_ids": ["uuid1", "uuid2", "uuid3"],
  "reviewed_by": "uuid",
  "reviewed_at": "2026-09-04T10:30:00",
  "review_notes": "Confirmed by analyst...",
  "created_at": "2026-09-04T10:00:00",
  "updated_at": "2026-09-04T10:30:00"
}
```

**Error (403):** Access denied (citizen viewing unverified event)
**Error (404):** Event not found

## System Endpoints

### GET /health
Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-04T10:30:00",
  "version": "0.5.0"
}
```

### GET /ready
Readiness check (includes database connectivity).

**Response (200 if ready):**
```json
{
  "status": "ready",
  "database": "connected",
  "timestamp": "2026-09-04T10:30:00"
}
```

**Response (503 if not ready):**
```json
{
  "status": "not_ready",
  "database": "disconnected",
  "error": "connection refused"
}
```

### GET /docs
Swagger UI documentation (interactive)

### GET /redoc
ReDoc API documentation (read-only)

## Error Handling

All error responses follow this format:

**Error Response:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200`: Success
- `400`: Bad request (invalid input)
- `401`: Unauthorized (missing/invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Not found
- `422`: Validation error (Pydantic validation failed)
- `500`: Internal server error

## Authentication

All endpoints except `/auth` require JWT bearer token authentication.

**Header:**
```
Authorization: Bearer <access_token>
```

**Token Lifespan:**
- Access token: 24 hours (configurable via JWT_EXPIRATION_HOURS)
- Refresh token: 7 days

## Rate Limiting

Not implemented in MVP. Future phases can add:
- Request rate limiting (e.g., 100 req/min per user)
- Concurrent report submission limits
- Database query throttling

## Data Model

### Evidence Status (System-Assigned, Frozen)
Assigned by Phase 3C verification_engine.py, based on correlation with meteorological evidence:
- `SUPPORTED` - weather evidence confirms report
- `CONFLICTING` - weather evidence contradicts report
- `UNVERIFIED` - evidence inconclusive
- `INSUFFICIENT_EVIDENCE` - no usable evidence

### Final Verification Status (Admin-Assigned, Phase 6)
Assigned by admin user after reviewing evidence:
- `VERIFIED` - admin confirmed event
- `NEEDS_REVIEW` - event pending admin review
- `REJECTED` - admin rejected event

### Roles
- `CITIZEN` - report submission, see verified events
- `ANALYST` - see all events, export data, view evidence
- `ADMIN` - full access (not yet implemented in Phase 5)

## Examples

### Flow 1: Citizen Submits Report
```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "citizen@test.com",
    "password": "password123",
    "role": "CITIZEN"
  }'

# Save access_token from response
TOKEN="eyJhbGc..."

# 2. Submit report (synchronous processing, ~1-3 seconds)
curl -X POST http://localhost:8000/reports \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Heavy rainfall near railway station",
    "city": "Jabalpur",
    "latitude": 23.1815,
    "longitude": 79.9864,
    "event_type": "RAINFALL"
  }'

# Response contains report_id, event_id, evidence_status

# 3. Check report status
REPORT_ID="<from response>"
curl -X GET "http://localhost:8000/reports/$REPORT_ID/status" \
  -H "Authorization: Bearer $TOKEN"

# 4. Check event details (if verified)
EVENT_ID="<from response>"
curl -X GET "http://localhost:8000/events/$EVENT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### Flow 2: Analyst Views Events
```bash
# 1. Register as analyst
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@test.com",
    "password": "password123",
    "role": "ANALYST"
  }'

# Save token
TOKEN="eyJhbGc..."

# 2. List all events (analyst sees all statuses)
curl -X GET "http://localhost:8000/events?limit=20" \
  -H "Authorization: Bearer $TOKEN"

# 3. Filter by severity
curl -X GET "http://localhost:8000/events?severity=HIGH&limit=50" \
  -H "Authorization: Bearer $TOKEN"

# 4. View event with evidence detail
EVENT_ID="<from list>"
curl -X GET "http://localhost:8000/events/$EVENT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

## Performance Notes

### Typical Latencies (MVP, Single Instance)
- POST /reports: 1-3 seconds (full pipeline execution)
- GET /events: 200-500 ms (PostGIS queries)
- GET /events/{id}: 100-300 ms (single record fetch)

### Scale Assumptions
- Single FastAPI instance
- Single PostgreSQL instance
- ~1k reports/day throughput

### Performance Considerations for Scale
- Phase 5 uses **synchronous-only** processing
- If POST /reports latency exceeds SLA, Phase 6+ can add:
  - Request queuing
  - Async processing with Celery
  - Caching layer
  - Database indexing optimization

## Implementation Notes

### Synchronous Processing (No Queue)
- POST /reports completes within request/response cycle
- Full pipeline runs synchronously (no background jobs)
- Response returns after PostgreSQL write completes
- Users get immediate feedback

### Phase 1-4C Integration
- Imports existing functions read-only
- Phase 3A normalization, Phase 3B classification, Phase 3C evidence scoring
- Does not modify existing Phase 1-4C code
- Falls back gracefully if Phase 1-4C unavailable

### Evidence Status Assignment
- Determined by Phase 3C verification_engine.py
- Based on correlation with ERA5/Open-Meteo meteorological data
- Never collapsed into binary true/false
- Always preserves all four states: SUPPORTED / CONFLICTING / UNVERIFIED / INSUFFICIENT_EVIDENCE

---

# Phase 6: Admin Verification Workflow

Backend-only admin review layer on top of Phase 5. No React UI (Phase 7).

## Core concept: two separate status fields

| Field | Set by | Values | Meaning |
|---|---|---|---|
| `evidence_status` | System (Phase 3C) | `SUPPORTED` / `CONFLICTING` / `UNVERIFIED` / `INSUFFICIENT_EVIDENCE` | What the automated cross-source comparison found |
| `final_verification_status` | Admin (Phase 6) | `VERIFIED` / `NEEDS_REVIEW` / `REJECTED` | What a human reviewer decided |

These never derive from one another. `CONFLICTING` evidence is not auto-rejected; an admin decides. Nothing in Phase 6 ever writes to `evidence_status`, and no evidence record is ever deleted.

All three endpoints below require `Authorization: Bearer <token>` for a user with `role=ADMIN`. Missing/invalid token → `401`. Valid token but wrong role → `403`.

## GET /admin/verification-queue

Paginated list of events for admin review.

**Query params:** `status` (default `NEEDS_REVIEW`; pass `ALL` for every status), `evidence_status`, `event_type`, `city`, `severity`, `start_date`, `end_date` (ISO 8601), `limit` (default 20, max 200), `offset`.

**Response (200):**
```json
{
  "items": [
    {
      "event_id": "uuid",
      "event_type": "RAINFALL",
      "location_name": "Jabalpur, Madhya Pradesh",
      "severity": "HIGH",
      "start_time": "2026-09-05T08:00:00Z",
      "evidence_status": "CONFLICTING",
      "evidence_support_score": 0.42,
      "final_verification_status": "NEEDS_REVIEW",
      "report_count": 2,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

## GET /admin/events/{event_id}/evidence

Full evidence package for one event: event summary, the raw Phase 3C `evidence_detail` (ERA5/IMD/Open-Meteo agreement, passed through unmodified as `external_evidence`), and every member `WeatherReport` (single query, no N+1). 404 if the event doesn't exist.

## POST /admin/events/{event_id}/verify

Submit a final verification decision.

**Request:**
```json
{
  "action": "VERIFIED",
  "notes": "Corroborated by IMD and multiple citizen reports."
}
```
`action` must be `VERIFIED` / `NEEDS_REVIEW` / `REJECTED` (anything else → `422`, enforced by the Pydantic schema before the handler runs). `notes` is **required** for `REJECTED` and `NEEDS_REVIEW` (→ `422` if missing/blank); optional for `VERIFIED`. `reviewed_by` always comes from the authenticated admin's JWT — it is never accepted from the request body.

**Response (200):**
```json
{
  "success": true,
  "event_id": "uuid",
  "previous_status": "NEEDS_REVIEW",
  "final_verification_status": "VERIFIED",
  "reviewed_by": "uuid",
  "reviewed_at": "2026-09-06T10:42:00Z",
  "notes": "Corroborated by IMD and multiple citizen reports."
}
```

**Errors:** `404` event not found · `422` invalid action / missing required notes · `500` on an unexpected DB error, in which case nothing is written (see transaction notes below).

### Transaction safety
The event update, the `AdminReviewAction` insert, and the `AuditLog` insert happen in a single SQLAlchemy transaction with one `db.commit()`; any exception triggers `db.rollback()` before the `500` is raised, so the event is never left updated without its audit trail. This is verified by `test_20_no_partial_writes_on_validation_failure`, which checks that a `422` (missing reason) leaves the event's status, and both audit tables, completely untouched — genuine mid-transaction fault injection (e.g. a dropped DB connection between the two inserts) is not simulated, since that isn't reliably triggerable in this environment; this is the tested boundary, not a claim of full fault-injection coverage.

## Database

**No new tables, no migration.** Phase 5's schema already had everything Phase 6 needs:
- `weather_events.final_verification_status` / `reviewed_by` / `reviewed_at` / `review_notes`
- `admin_review_actions` (immutable per-decision audit row)
- `audit_log` (generic WHO/WHAT/WHEN/WHY trail)

Phase 6 only **appends** new Pydantic response/request schemas to the end of `phase5/api/schemas.py` (nothing existing is changed) and adds `phase5/api/routes/admin.py`, registered in `main.py` alongside the existing routers.

## RBAC

Uses the existing `require_admin` dependency from `phase5/api/auth/rbac.py` (already defined in Phase 5, previously untested by any route — Phase 6 is its first real consumer). CITIZEN and ANALYST get `403` on all three endpoints; unauthenticated requests get `401`.

## Testing

`phase5/tests/test_phase6_admin_verification.py` — 24 tests: 8 auth/RBAC, 9 verification-decision behaviors (VERIFIED/NEEDS_REVIEW/REJECTED, invalid status, nonexistent event, reason validation, previous-status capture, AdminReviewAction creation, AuditLog creation), 3 persistence (survives a fresh DB connection, audit data matches the decision, no partial writes on validation failure), and 4 bonus queue-filtering tests.

Run: `pytest phase5/tests/ -v` → **63 passed** (39 existing Phase 5 + 24 new Phase 6), 0 failed. Full project regression (`pytest tests/ -q` for Phase 1-4C + `pytest phase5/tests/ -v` for Phase 5-6) → **238 passed, 0 failed.**
