-- MuleCatch PostgreSQL Schema
-- Replaces in-memory repositories with durable storage.

-- ── STR Reports ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS str_reports (
    str_id      TEXT PRIMARY KEY,
    alert_ids   JSONB NOT NULL DEFAULT '[]',
    account_ids JSONB NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'DRAFT',
    narrative   TEXT NOT NULL DEFAULT '',
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    risk_score  DOUBLE PRECISION NOT NULL DEFAULT 0,
    gnn_score   DOUBLE PRECISION,
    reason_codes JSONB NOT NULL DEFAULT '[]',
    reporting_entity TEXT NOT NULL DEFAULT '',
    reporting_ifsc   TEXT NOT NULL DEFAULT '',
    prepared_by      TEXT NOT NULL DEFAULT '',
    approved_by      TEXT,
    fiu_reference    TEXT,
    fiu_format_version TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at    TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_str_status ON str_reports(status);

-- ── Audit Logs (append-only) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id      TEXT PRIMARY KEY,
    action      TEXT NOT NULL,
    username    TEXT NOT NULL DEFAULT '',
    alert_id    TEXT,
    details     TEXT,
    previous_hash TEXT NOT NULL DEFAULT '',
    entry_hash  TEXT NOT NULL DEFAULT '',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_alert  ON audit_logs(alert_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit_logs(timestamp DESC);

-- ── Escalations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    escalation_id TEXT PRIMARY KEY,
    alert_id      TEXT NOT NULL,
    reason        TEXT NOT NULL DEFAULT '',
    priority      TEXT NOT NULL DEFAULT 'MEDIUM',
    status        TEXT NOT NULL DEFAULT 'PENDING',
    user_id       TEXT,
    resolved_by   TEXT,
    resolved_action TEXT,
    resolution_notes TEXT,
    escalated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_esc_status ON escalations(status);

-- ── Screening Results ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screening_results (
    result_id   TEXT PRIMARY KEY,
    account_id  TEXT NOT NULL,
    screened_name TEXT NOT NULL DEFAULT '',
    matches     JSONB NOT NULL DEFAULT '[]',
    match_count INTEGER NOT NULL DEFAULT 0,
    highest_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'CLEAR',
    screened_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_screen_account ON screening_results(account_id);

-- ── Screening Watchlist ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screening_watchlist (
    entry_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    aliases     JSONB NOT NULL DEFAULT '[]',
    identifiers JSONB NOT NULL DEFAULT '[]',
    entity_type TEXT NOT NULL DEFAULT 'INDIVIDUAL',
    countries   JSONB NOT NULL DEFAULT '[]',
    risk_category TEXT NOT NULL DEFAULT 'SANCTIONS',
    source      TEXT NOT NULL DEFAULT '',
    date_of_birth TEXT,
    added_date  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_watchlist_source ON screening_watchlist(source);
CREATE INDEX IF NOT EXISTS idx_watchlist_name   ON screening_watchlist(LOWER(name));

-- ── Onboarding Assessments ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_assessments (
    assessment_id TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    risk_score    DOUBLE PRECISION NOT NULL DEFAULT 0,
    risk_level    TEXT NOT NULL DEFAULT 'LOW',
    signals       JSONB NOT NULL DEFAULT '[]',
    reason_codes  JSONB NOT NULL DEFAULT '[]',
    recommendation TEXT NOT NULL DEFAULT '',
    entity_resolution JSONB NOT NULL DEFAULT '{}',
    assessed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_onboard_account ON onboarding_assessments(account_id);
CREATE INDEX IF NOT EXISTS idx_onboard_risk    ON onboarding_assessments(risk_level);

-- Privacy-minimised identity profiles for duplicate/synthetic identity linking.
-- Phone/email values are one-way hashed by the application before persistence.
CREATE TABLE IF NOT EXISTS identity_profiles (
    entity_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT '',
    phone_hash TEXT NOT NULL DEFAULT '',
    email_hash TEXT NOT NULL DEFAULT '',
    postal_address TEXT NOT NULL DEFAULT '',
    government_id_hash TEXT NOT NULL DEFAULT '',
    device_fingerprint TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_identity_phone  ON identity_profiles(phone_hash);
CREATE INDEX IF NOT EXISTS idx_identity_email  ON identity_profiles(email_hash);
CREATE INDEX IF NOT EXISTS idx_identity_gov    ON identity_profiles(government_id_hash);
CREATE INDEX IF NOT EXISTS idx_identity_device ON identity_profiles(device_fingerprint);

-- ── KPI Snapshots ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id          SERIAL PRIMARY KEY,
    total_alerts INTEGER NOT NULL DEFAULT 0,
    false_positives_avoided INTEGER NOT NULL DEFAULT 0,
    hours_saved DOUBLE PRECISION NOT NULL DEFAULT 0,
    fraud_prevented_inr DOUBLE PRECISION NOT NULL DEFAULT 0,
    investigation_time_reduction_pct INTEGER NOT NULL DEFAULT 75,
    strs_filed  INTEGER NOT NULL DEFAULT 0,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Monthly Trends (ROI dashboard) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS monthly_trends (
    month       TEXT UNIQUE NOT NULL,
    alerts      INTEGER NOT NULL DEFAULT 0,
    prevented   DOUBLE PRECISION NOT NULL DEFAULT 0,
    hours       DOUBLE PRECISION NOT NULL DEFAULT 0
);

-- ── Detection Breakdown (ROI dashboard) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS detection_breakdown (
    pattern     TEXT UNIQUE NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0
);

-- ── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'READONLY',
    display_name TEXT NOT NULL DEFAULT '',
    branch      TEXT NOT NULL DEFAULT '',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login  TIMESTAMPTZ
);

-- ── Failed Logins ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS failed_logins (
    id           SERIAL PRIMARY KEY,
    username     TEXT NOT NULL,
    attempt_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip_address   TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_failed_logins_user ON failed_logins(username, attempt_time);

-- Seed initial KPI snapshot row
INSERT INTO kpi_snapshots (total_alerts, false_positives_avoided, hours_saved, fraud_prevented_inr, strs_filed)
SELECT 0, 0, 0, 0, 0
WHERE NOT EXISTS (SELECT 1 FROM kpi_snapshots LIMIT 1);
