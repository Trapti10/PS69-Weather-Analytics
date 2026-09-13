-- PS69 Weather Analytics Phase 5 Schema
-- PostgreSQL 15 + PostGIS 3.3
-- 6 tables: users, weather_reports, weather_events, admin_review_actions, alerts, audit_log

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS & AUTH
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) CHECK(role IN ('CITIZEN', 'ANALYST', 'ADMIN')) DEFAULT 'CITIZEN',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 2. WEATHER REPORTS (from Phase 3A, migrated to DB)
CREATE TABLE IF NOT EXISTS weather_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50),                     -- SOCIAL_MEDIA, CITIZEN_REPORT, API, etc.
    source_name VARCHAR(100),
    author_id_or_hash VARCHAR(255),              -- hashed
    report_timestamp TIMESTAMP,
    ingestion_timestamp TIMESTAMP DEFAULT NOW(),
    city VARCHAR(100),
    state VARCHAR(100),
    location GEOMETRY(Point, 4326),              -- PostGIS point (lat, lon)
    text TEXT,
    image_url VARCHAR(500),
    video_url VARCHAR(500),
    event_type VARCHAR(50),                      -- RAINFALL, THUNDERSTORM, etc.
    raw_event_type VARCHAR(100),
    verification_status VARCHAR(20),             -- UNVERIFIED, VERIFIED, REJECTED, SUSPICIOUS (structural)
    source_reliability NUMERIC(3, 2),
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_hash VARCHAR(255),
    event_id UUID,                               -- FK to weather_events (set after event creation)
    is_suspicious BOOLEAN DEFAULT FALSE,
    
    -- Phase 3B: Intelligence
    semantic_similarity_score NUMERIC(3, 2),
    predicted_event_category VARCHAR(50),
    event_classification_confidence NUMERIC(3, 2),
    risk_score NUMERIC(3, 2),
    risk_label VARCHAR(50),
    
    raw_payload JSONB,                           -- JSON of original ingested data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_reports_location ON weather_reports USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_weather_reports_event ON weather_reports(event_id);
CREATE INDEX IF NOT EXISTS idx_weather_reports_timestamp ON weather_reports(report_timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_reports_hash ON weather_reports(duplicate_hash);
CREATE INDEX IF NOT EXISTS idx_weather_reports_source ON weather_reports(source_type, source_name);

-- 3. WEATHER EVENTS (NEW - core entity)
CREATE TABLE IF NOT EXISTS weather_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50),                      -- RAINFALL, FLOODING, HEATWAVE, etc.
    location GEOMETRY(Point, 4326),              -- PostGIS centroid of event
    location_name VARCHAR(255),                  -- city / state / region
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    severity VARCHAR(20) CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'EXTREME')) DEFAULT 'MEDIUM',
    
    -- Evidence Status (from Phase 3C - FROZEN)
    evidence_status VARCHAR(50) CHECK(evidence_status IN ('SUPPORTED', 'CONFLICTING', 'UNVERIFIED', 'INSUFFICIENT_EVIDENCE')),
    evidence_support_score NUMERIC(3, 2),       -- 0.0-1.0, NULL if no evidence
    evidence_detail JSONB,                       -- SourceVerdict list and thresholds
    
    -- Final Verification Status (Admin decision)
    final_verification_status VARCHAR(20) CHECK(final_verification_status IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED')) DEFAULT 'NEEDS_REVIEW',
    
    -- Member Reports
    member_report_ids UUID[] DEFAULT ARRAY[]::UUID[],  -- array of report_id values
    report_count INTEGER DEFAULT 0,
    unique_sources INTEGER DEFAULT 0,           -- count of distinct sources
    
    -- Admin Review Audit Trail
    reviewed_by UUID REFERENCES users(user_id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_events_location ON weather_events USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_weather_events_time ON weather_events(start_time);
CREATE INDEX IF NOT EXISTS idx_weather_events_status ON weather_events(evidence_status, final_verification_status);
CREATE INDEX IF NOT EXISTS idx_weather_events_severity ON weather_events(severity);

-- Add the report -> event foreign key after both tables exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_weather_reports_event'
    ) THEN
        ALTER TABLE weather_reports
            ADD CONSTRAINT fk_weather_reports_event
            FOREIGN KEY (event_id) REFERENCES weather_events(event_id);
    END IF;
END $$;

-- 4. ADMIN REVIEW ACTIONS (audit log)
CREATE TABLE IF NOT EXISTS admin_review_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES weather_events(event_id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES users(user_id),
    action VARCHAR(50) CHECK(action IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED', 'NOTE_ADDED', 'STATUS_CHANGED')),
    notes TEXT,
    evidence_summary JSONB,                      -- JSON summary of what was reviewed
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_review_event ON admin_review_actions(event_id);
CREATE INDEX IF NOT EXISTS idx_admin_review_admin ON admin_review_actions(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_review_action ON admin_review_actions(action);

-- 5. ALERTS
CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES weather_events(event_id) ON DELETE CASCADE,
    severity_threshold VARCHAR(20),
    alert_status VARCHAR(20) CHECK(alert_status IN ('TRIGGERED', 'SENT', 'ACKNOWLEDGED', 'EXPIRED')) DEFAULT 'TRIGGERED',
    channel VARCHAR(50),                         -- SMS, EMAIL, CONSOLE, WEBHOOK
    message TEXT,
    recipient_id UUID REFERENCES users(user_id),  -- NULL for broadcast
    triggered_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_event ON alerts(event_id);
CREATE INDEX IF NOT EXISTS idx_alerts_recipient ON alerts(recipient_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(alert_status);

-- 6. AUDIT LOG (all changes)
CREATE TABLE IF NOT EXISTS audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50),                     -- WEATHER_EVENT, WEATHER_REPORT, USER, ALERT
    entity_id UUID,
    action VARCHAR(50),                          -- CREATE, UPDATE, DELETE, VERIFY, REJECT
    actor_id UUID REFERENCES users(user_id),
    changes JSONB,                               -- JSON diff
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

-- COMMENTS
COMMENT ON TABLE weather_events IS 'Central aggregate: groups related reports, carries evidence_status + final_verification_status + audit trail';
COMMENT ON COLUMN weather_events.evidence_status IS 'System-assigned (Phase 3C): SUPPORTED / CONFLICTING / UNVERIFIED / INSUFFICIENT_EVIDENCE - never collapsed to binary';
COMMENT ON COLUMN weather_events.final_verification_status IS 'Admin-assigned: VERIFIED / NEEDS_REVIEW / REJECTED - separate from evidence_status';
COMMENT ON TABLE admin_review_actions IS 'Immutable audit log: every admin decision is traceable';
COMMENT ON TABLE audit_log IS 'Change tracking: every state change logged with actor, timestamp, and delta';

-- 7. WEATHER OBSERVATIONS (analytics intelligence layer)
-- Populated from the real Phase 1-2C sensor datasets (ERA5 reanalysis,
-- Open-Meteo API) by backend/db/ingest_analytics_data.py. This is
-- deliberately separate from weather_events/weather_reports: those are the
-- citizen-report/verification pipeline (Phase 3-6), this is the raw
-- collected scientific observation record the platform was built to surface.
CREATE TABLE IF NOT EXISTS weather_observations (
    id UUID PRIMARY KEY,                          -- carried over from the source dataset's own id column (stable across re-runs -> idempotent upsert key)
    source VARCHAR(50) NOT NULL,                  -- e.g. ERA5, Open-Meteo (exactly what the source file's `source` column says)
    observed_at TIMESTAMP NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_name VARCHAR(255),                   -- NULL: source CSVs have no place-name column, only raw lat/lon (see ingest_analytics_data.py)
    temperature DOUBLE PRECISION,                  -- degrees C
    humidity DOUBLE PRECISION,                     -- percent; not present in every source (e.g. ERA5 fused records have none)
    rainfall DOUBLE PRECISION,                     -- mm
    wind_speed DOUBLE PRECISION,                   -- m/s
    wind_direction DOUBLE PRECISION,                -- degrees
    pressure DOUBLE PRECISION,                     -- hPa
    verification_status VARCHAR(20),               -- as recorded by the Phase 2 fusion step (e.g. 'validated')
    confidence_score NUMERIC(3, 2),
    quality_flags TEXT,
    location GEOMETRY(Point, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_observations_observed_at ON weather_observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_observations_source ON weather_observations(source);
CREATE INDEX IF NOT EXISTS idx_weather_observations_location ON weather_observations USING GIST (location);

COMMENT ON TABLE weather_observations IS 'Real ERA5 + Open-Meteo sensor observations (Phase 2/2C fusion output), ingested for database-backed analytics. NOT the citizen-report pipeline.';

-- 8. WEATHER ANOMALIES (analytics intelligence layer)
-- Populated from the Phase 4C statistical anomaly detection output
-- (rolling z-score / rainfall-ratio methods against each source's own
-- history). Every row here is already a flagged anomaly, not a raw
-- evaluated observation - the source file only contains flagged rows.
CREATE TABLE IF NOT EXISTS weather_anomalies (
    id UUID PRIMARY KEY,                          -- carried over from data/phase4c/anomalies.csv `id`
    source VARCHAR(50) NOT NULL,                  -- ERA5, Open-Meteo
    observed_at TIMESTAMP NOT NULL,               -- when the anomalous reading occurred (source file `timestamp`)
    detected_at TIMESTAMP,                        -- when Phase 4C's detector produced this record (source file `generated_at`)
    variable VARCHAR(50) NOT NULL,                -- temperature, rainfall, wind_speed, pressure
    observed_value DOUBLE PRECISION,
    baseline_value DOUBLE PRECISION,
    deviation DOUBLE PRECISION,
    method VARCHAR(50),                           -- e.g. rolling_zscore
    threshold DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    severity VARCHAR(20) CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),  -- Phase 4C's own vocabulary - distinct from weather_events.severity (LOW/MEDIUM/HIGH/EXTREME); do not conflate the two
    classification VARCHAR(50),                   -- e.g. STATISTICAL_ANOMALY
    status VARCHAR(20),                           -- e.g. EVALUATED
    explanation TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_name VARCHAR(255),
    location GEOMETRY(Point, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_anomalies_observed_at ON weather_anomalies(observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_anomalies_variable ON weather_anomalies(variable);
CREATE INDEX IF NOT EXISTS idx_weather_anomalies_severity ON weather_anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_weather_anomalies_source ON weather_anomalies(source);
CREATE INDEX IF NOT EXISTS idx_weather_anomalies_location ON weather_anomalies USING GIST (location);

COMMENT ON TABLE weather_anomalies IS 'Flagged statistical anomalies from Phase 4C (rolling z-score / rainfall-ratio detection against each source''s own history), ingested for database-backed analytics.';

