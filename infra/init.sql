-- ============================================================
-- TACO MVP — Database Initialization
-- ============================================================

-- ── Table 1: request_logs ────────────────────────────────────
CREATE TABLE IF NOT EXISTS request_logs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               VARCHAR(255) NOT NULL,
    org_id                VARCHAR(255),
    task_type             VARCHAR(50),
    provider              VARCHAR(50),
    model_requested       VARCHAR(100),
    model_used            VARCHAR(100),
    prompt_tokens         INTEGER,
    completion_tokens     INTEGER,
    total_tokens          INTEGER,
    cost_usd              DECIMAL(10, 8),
    latency_ms            INTEGER,
    was_sliced            BOOLEAN DEFAULT FALSE,
    messages_original_count INTEGER,
    messages_sent_count   INTEGER,
    status_code           INTEGER,
    error_message         TEXT,
    created_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_logs_user_created
    ON request_logs (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_request_logs_org_created
    ON request_logs (org_id, created_at);

CREATE INDEX IF NOT EXISTS idx_request_logs_model_created
    ON request_logs (model_used, created_at);

CREATE INDEX IF NOT EXISTS idx_request_logs_created
    ON request_logs (created_at);

-- ── Table 2: model_pricing ───────────────────────────────────
CREATE TABLE IF NOT EXISTS model_pricing (
    id                   SERIAL PRIMARY KEY,
    provider             VARCHAR(50) NOT NULL,
    model                VARCHAR(100) NOT NULL UNIQUE,
    tier                 VARCHAR(20) NOT NULL,
    input_cost_per_1k    DECIMAL(10, 8) NOT NULL,
    output_cost_per_1k   DECIMAL(10, 8) NOT NULL,
    context_window       INTEGER NOT NULL,
    is_active            BOOLEAN DEFAULT TRUE,
    updated_at           TIMESTAMP DEFAULT NOW()
);

-- Seed pricing data (approximate — verify before go-live)
INSERT INTO model_pricing (provider, model, tier, input_cost_per_1k, output_cost_per_1k, context_window) VALUES
    ('openai',    'gpt-4o-mini',               'cheap', 0.00015000, 0.00060000, 128000),
    ('openai',    'gpt-4o',                    'smart', 0.00250000, 0.01000000, 128000),
    ('anthropic', 'claude-haiku-4-5-20251001', 'cheap', 0.00080000, 0.00400000, 200000),
    ('anthropic', 'claude-sonnet-4-6',         'smart', 0.00300000, 0.01500000, 200000),
    ('google',    'gemini-1.5-flash',          'cheap', 0.00007500, 0.00030000, 1000000),
    ('google',    'gemini-1.5-pro',            'smart', 0.00125000, 0.00500000, 1000000)
ON CONFLICT (model) DO NOTHING;

-- Update google models to be inactive by default so router picks OpenAI
UPDATE model_pricing SET is_active = FALSE WHERE provider = 'google';

-- ── Table 3: budgets ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budgets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type  VARCHAR(20) NOT NULL,   -- 'user' or 'org'
    entity_id    VARCHAR(255) NOT NULL,
    limit_usd    DECIMAL(10, 4) NOT NULL,
    period       VARCHAR(20) NOT NULL,   -- 'daily' | 'weekly' | 'monthly'
    action       VARCHAR(20) NOT NULL,   -- 'block' | 'alert'
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
