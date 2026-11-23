BEGIN;

CREATE TABLE IF NOT EXISTS public.adventure_journeys (
    user_id bigint PRIMARY KEY,
    region integer NOT NULL DEFAULT 1 CHECK (region BETWEEN 1 AND 8),
    distance double precision NOT NULL DEFAULT 0 CHECK (distance BETWEEN 0 AND 18),
    direction text NOT NULL CHECK (direction IN ('north','south','east','west','northeast')),
    energy integer NOT NULL CHECK (energy BETWEEN 1 AND 5),
    last_mood_id bigint NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.adventure_puzzle_progress (
    user_id bigint NOT NULL,
    region integer NOT NULL CHECK (region BETWEEN 1 AND 8),
    gate integer NOT NULL CHECK (gate BETWEEN 1 AND 5),
    status text NOT NULL CHECK (status IN ('playing','cooldown','completed')),
    started_at timestamptz,
    deadline_at timestamptz,
    cooldown_until timestamptz,
    completed_at timestamptz,
    attempt_count integer NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, region, gate)
);

ALTER TABLE public.adventure_journeys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.adventure_puzzle_progress ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.adventure_journeys, public.adventure_puzzle_progress FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.adventure_journeys, public.adventure_puzzle_progress TO service_role;

ALTER TABLE public.adventure_puzzle_progress
    ADD COLUMN IF NOT EXISTS moves jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS verified_at timestamptz;

-- Invalidate legacy completions accepted from the former client completion flag.
-- Move only affected journeys back to their first unverified checkpoint.
WITH checkpoint AS (
    SELECT DISTINCT ON (user_id) user_id, region, gate
    FROM public.adventure_puzzle_progress
    WHERE status = 'completed' AND verified_at IS NULL
    ORDER BY user_id, region, gate
)
UPDATE public.adventure_journeys j
SET region = c.region, distance = CASE WHEN c.region < j.region THEN c.gate * 3
    ELSE LEAST(j.distance, c.gate * 3) END, updated_at = clock_timestamp()
FROM checkpoint c
WHERE j.user_id = c.user_id AND c.region <= j.region;

UPDATE public.adventure_puzzle_progress
SET status = 'cooldown', cooldown_until = clock_timestamp(),
    completed_at = NULL, attempt_count = 0, moves = '[]', revision = revision + 1
WHERE status = 'completed' AND verified_at IS NULL;

ALTER TABLE public.adventure_puzzle_progress
    DROP CONSTRAINT IF EXISTS adventure_completed_requires_verification;
ALTER TABLE public.adventure_puzzle_progress
    ADD CONSTRAINT adventure_completed_requires_verification
    CHECK (status::text <> 'completed' OR verified_at IS NOT NULL);

CREATE OR REPLACE FUNCTION public.adventure_gate_v1(
    p_user_id bigint, p_region integer, p_gate integer, p_operation text,
    p_attempt integer DEFAULT NULL, p_revision integer DEFAULT NULL,
    p_move text DEFAULT NULL, p_correct boolean DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    j public.adventure_journeys%ROWTYPE;
    g public.adventure_puzzle_progress%ROWTYPE;
    ts timestamptz;
    changed boolean := false;
    failure text;
    next_status public.adventure_puzzle_progress.status%TYPE;
    minutes integer[] := ARRAY[5,8,10,15,20];
BEGIN
    IF p_region NOT BETWEEN 1 AND 8 OR p_gate NOT BETWEEN 1 AND 5 THEN
        RETURN jsonb_build_object('error', 'unknown');
    END IF;
    -- Same lock order for read, open, move, submit and region transition.
    SELECT * INTO j FROM public.adventure_journeys WHERE user_id = p_user_id FOR UPDATE;
    SELECT * INTO g FROM public.adventure_puzzle_progress
    WHERE user_id = p_user_id AND region = p_region AND gate = p_gate FOR UPDATE;
    ts := clock_timestamp();

    IF g.status = 'playing' AND g.deadline_at <= ts THEN
        UPDATE public.adventure_puzzle_progress
        SET status = 'cooldown', cooldown_until = g.deadline_at + interval '8 hours',
            moves = '[]', revision = g.revision + 1
        WHERE user_id = p_user_id AND region = p_region AND gate = p_gate RETURNING * INTO g;
    END IF;

    IF p_operation <> 'read' THEN
        IF j.region IS DISTINCT FROM p_region OR j.distance < p_gate * 3 OR EXISTS (
            SELECT 1 FROM generate_series(1, p_gate - 1) AS predecessor(gate)
            WHERE NOT EXISTS (
                SELECT 1 FROM public.adventure_puzzle_progress p
                WHERE p.user_id = p_user_id AND p.region = p_region
                    AND p.gate = predecessor.gate AND p.status = 'completed'
                    AND p.verified_at IS NOT NULL
            )
        ) THEN
            failure := 'locked';
        ELSIF p_operation = 'open' THEN
            IF g.status IS NULL OR g.status::text = 'pending' OR (g.status = 'cooldown' AND g.cooldown_until <= ts) THEN
                INSERT INTO public.adventure_puzzle_progress (
                    user_id, region, gate, status, started_at, deadline_at, attempt_count
                ) VALUES (
                    p_user_id, p_region, p_gate, 'playing', ts,
                    ts + make_interval(mins => minutes[p_gate]), 1
                ) ON CONFLICT (user_id, region, gate) DO UPDATE
                SET status = 'playing', started_at = EXCLUDED.started_at,
                    deadline_at = EXCLUDED.deadline_at, cooldown_until = NULL,
                    completed_at = NULL, verified_at = NULL, moves = '[]',
                    attempt_count = adventure_puzzle_progress.attempt_count + 1,
                    revision = adventure_puzzle_progress.revision + 1
                RETURNING * INTO g;
                changed := true;
            END IF;
        ELSIF g.status = 'playing' THEN
            IF g.attempt_count IS DISTINCT FROM p_attempt OR g.revision IS DISTINCT FROM p_revision THEN
                failure := 'stale';
            ELSIF p_operation = 'move' AND jsonb_array_length(g.moves) >= 256 THEN
                failure := 'move_limit';
            ELSIF p_operation = 'move' OR p_operation = 'reset' THEN
                UPDATE public.adventure_puzzle_progress
                SET moves = CASE WHEN p_operation = 'reset' THEN '[]'::jsonb ELSE g.moves || jsonb_build_array(p_move) END,
                    revision = g.revision + 1
                WHERE user_id = p_user_id AND region = p_region AND gate = p_gate RETURNING * INTO g;
                changed := true;
            ELSIF p_operation = 'submit' AND p_correct IS NOT NULL THEN
                IF p_correct THEN next_status := 'completed';
                ELSE next_status := 'cooldown'; END IF;
                UPDATE public.adventure_puzzle_progress
                SET status = next_status,
                    completed_at = CASE WHEN p_correct THEN ts END,
                    verified_at = CASE WHEN p_correct THEN ts END,
                    cooldown_until = CASE WHEN NOT p_correct THEN ts + interval '8 hours' END,
                    revision = g.revision + 1, moves = '[]'
                WHERE user_id = p_user_id AND region = p_region AND gate = p_gate RETURNING * INTO g;
                IF p_correct THEN
                    UPDATE public.adventure_journeys
                    SET updated_at = ts
                    WHERE user_id = p_user_id;
                END IF;
                changed := true;
            ELSE
                failure := 'invalid';
            END IF;
        END IF;
    END IF;

    RETURN jsonb_build_object('row', CASE WHEN g.user_id IS NULL THEN NULL ELSE to_jsonb(g) END,
        'now', ts, 'changed', changed, 'error', failure,
        'retryReady', COALESCE(g.status = 'cooldown' AND g.cooldown_until <= ts, false));
END;
$$;

CREATE OR REPLACE FUNCTION public.adventure_next_region_v1(p_user_id bigint, p_region integer)
RETURNS boolean
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    j public.adventure_journeys%ROWTYPE;
BEGIN
    SELECT * INTO j FROM public.adventure_journeys WHERE user_id = p_user_id FOR UPDATE;
    IF j.region = p_region + 1 THEN RETURN true; END IF;
    IF j.region IS DISTINCT FROM p_region OR p_region NOT BETWEEN 1 AND 7 OR j.distance < 18 OR (
        SELECT count(*) FROM public.adventure_puzzle_progress
        WHERE user_id = p_user_id AND region = p_region AND gate BETWEEN 1 AND 5
            AND status = 'completed' AND verified_at IS NOT NULL
    ) <> 5 THEN RETURN false; END IF;
    UPDATE public.adventure_journeys SET region = p_region + 1, distance = 0,
        updated_at = clock_timestamp() WHERE user_id = p_user_id;
    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION public.adventure_gate_v1(bigint, integer, integer, text, integer, integer, text, boolean)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.adventure_next_region_v1(bigint, integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.adventure_gate_v1(bigint, integer, integer, text, integer, integer, text, boolean)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.adventure_next_region_v1(bigint, integer) TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;
