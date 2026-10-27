-- =============================================================================
-- Enterprise Industrial Hazardous Gas Leakage Detection & Containment System
-- Database Schema, Security Policies & Realtime Event Stream Configuration
-- =============================================================================

-- 1. TELEMETRY STORAGE TABLE
CREATE TABLE IF NOT EXISTS public.gas_telemetry (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    ppm INT4 NOT NULL CHECK (ppm >= 0),
    status TEXT NOT NULL CHECK (status IN ('NORMAL', 'WARNING', 'CRITICAL'))
);

-- Optimize time-series chronological queries
CREATE INDEX IF NOT EXISTS idx_gas_telemetry_created_at 
    ON public.gas_telemetry (created_at DESC);

-- 2. SUPERVISORY ACTUATOR & DEVICE CONTROLS TABLE
CREATE TABLE IF NOT EXISTS public.device_controls (
    id INT PRIMARY KEY,
    valve_state TEXT NOT NULL CHECK (valve_state IN ('OPEN', 'CLOSED')),
    fan_state TEXT NOT NULL CHECK (fan_state IN ('ON', 'OFF')),
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Seed default primary RTU control register (ID: 1)
INSERT INTO public.device_controls (id, valve_state, fan_state, updated_at)
VALUES (1, 'OPEN', 'OFF', TIMEZONE('utc'::text, NOW()))
ON CONFLICT (id) DO NOTHING;

-- 3. AUTOMATIC TIMESTAMP TRIGGER FOR DEVICE CONTROLS
CREATE OR REPLACE FUNCTION public.update_device_controls_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_device_controls_timestamp ON public.device_controls;
CREATE TRIGGER trg_update_device_controls_timestamp
    BEFORE UPDATE ON public.device_controls
    FOR EACH ROW
    EXECUTE FUNCTION public.update_device_controls_timestamp();

-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- Enabling permissive RLS for operational industrial SCADA bus & edge node bridge
ALTER TABLE public.gas_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_controls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access on gas_telemetry"
    ON public.gas_telemetry FOR SELECT
    USING (true);

CREATE POLICY "Allow telemetry ingestion on gas_telemetry"
    ON public.gas_telemetry FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Allow public read access on device_controls"
    ON public.device_controls FOR SELECT
    USING (true);

CREATE POLICY "Allow supervisory updates on device_controls"
    ON public.device_controls FOR UPDATE
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow edge bridge inserts on device_controls"
    ON public.device_controls FOR INSERT
    WITH CHECK (true);

-- 5. REALTIME REPLICATION PUBLICATION
-- Ensure full row payload publication for real-time change detection
ALTER TABLE public.gas_telemetry REPLICA IDENTITY FULL;
ALTER TABLE public.device_controls REPLICA IDENTITY FULL;

-- Publish tables to Supabase Realtime event bus
BEGIN;
    DROP PUBLICATION IF EXISTS supabase_realtime;
    CREATE PUBLICATION supabase_realtime FOR TABLE public.gas_telemetry, public.device_controls;
COMMIT;
