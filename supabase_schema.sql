-- ============================================================
-- Fitness Tracker — Supabase Database Schema
-- ============================================================
-- Apply via the Supabase SQL Editor (Dashboard → SQL Editor → New query).
-- Row-Level Security (RLS) policies restrict every user to their own data.
-- ============================================================

-- Enable the pgcrypto extension for gen_random_uuid() if not already enabled.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- TABLE: workouts
-- Top-level session that groups lifts OR a run under one date.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workouts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title         TEXT        NOT NULL,
    workout_type  TEXT        NOT NULL CHECK (workout_type IN ('lifting', 'run', 'mixed')),
    date          DATE        NOT NULL DEFAULT CURRENT_DATE,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE workouts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own workouts"
    ON workouts
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Automatically keep updated_at current.
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER workouts_updated_at
    BEFORE UPDATE ON workouts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────
-- TABLE: lifts
-- Individual exercises performed inside a lifting workout.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lifts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id    UUID        NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    exercise_name TEXT        NOT NULL,
    sets          INTEGER     NOT NULL CHECK (sets > 0),
    reps          INTEGER     NOT NULL CHECK (reps > 0),
    weight_kg     NUMERIC(7,2) NOT NULL DEFAULT 0 CHECK (weight_kg >= 0),
    rpe           NUMERIC(3,1) CHECK (rpe BETWEEN 1 AND 10),   -- Rate of Perceived Exertion
    notes         TEXT,
    logged_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE lifts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own lifts"
    ON lifts
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ─────────────────────────────────────────────────────────────
-- TABLE: runs
-- Track/road/trail run sessions with pace and distance data.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id        UUID        NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    user_id           UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    run_type          TEXT        NOT NULL CHECK (run_type IN ('track', 'road', 'trail', 'treadmill')),
    distance_km       NUMERIC(7,3) NOT NULL CHECK (distance_km > 0),
    duration_seconds  INTEGER     NOT NULL CHECK (duration_seconds > 0),
    -- Derived column stored for fast analytics queries.
    pace_sec_per_km   NUMERIC(7,2) GENERATED ALWAYS AS
                          (duration_seconds::NUMERIC / distance_km) STORED,
    avg_heart_rate    INTEGER     CHECK (avg_heart_rate BETWEEN 30 AND 250),
    max_heart_rate    INTEGER     CHECK (max_heart_rate BETWEEN 30 AND 250),
    elevation_gain_m  NUMERIC(7,1) DEFAULT 0,
    notes             TEXT,
    logged_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own runs"
    ON runs
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ─────────────────────────────────────────────────────────────
-- INDEXES  (improve dashboard query performance)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_workouts_user_date   ON workouts (user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_lifts_workout        ON lifts    (workout_id);
CREATE INDEX IF NOT EXISTS idx_lifts_user           ON lifts    (user_id);
CREATE INDEX IF NOT EXISTS idx_runs_workout         ON runs     (workout_id);
CREATE INDEX IF NOT EXISTS idx_runs_user_logged     ON runs     (user_id, logged_at DESC);

-- ─────────────────────────────────────────────────────────────
-- VIEWS  (convenience for the Analytics Dashboard)
-- ─────────────────────────────────────────────────────────────

-- Weekly running pace trend (used by the line graph).
CREATE OR REPLACE VIEW v_weekly_pace AS
SELECT
    user_id,
    DATE_TRUNC('week', logged_at)::DATE AS week_start,
    ROUND(AVG(pace_sec_per_km))         AS avg_pace_sec_per_km,
    SUM(distance_km)                    AS total_distance_km,
    COUNT(*)                            AS run_count
FROM runs
GROUP BY user_id, DATE_TRUNC('week', logged_at);

-- Workout volume by type in the last 30 days (used by the pie chart).
CREATE OR REPLACE VIEW v_volume_distribution AS
SELECT
    w.user_id,
    w.workout_type,
    COUNT(DISTINCT w.id)                               AS session_count,
    COALESCE(SUM(l.sets * l.reps * l.weight_kg), 0)   AS total_lift_volume_kg,
    COALESCE(SUM(r.distance_km), 0)                    AS total_run_km
FROM workouts w
LEFT JOIN lifts l ON l.workout_id = w.id
LEFT JOIN runs  r ON r.workout_id = w.id
WHERE w.date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY w.user_id, w.workout_type;
