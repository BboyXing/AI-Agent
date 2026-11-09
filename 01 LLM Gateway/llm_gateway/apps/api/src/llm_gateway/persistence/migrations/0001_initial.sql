CREATE TABLE IF NOT EXISTS llm_requests (
    request_id TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    route TEXT NOT NULL,
    prompt TEXT NOT NULL,
    stream INTEGER NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    selected_candidate TEXT,
    provider TEXT,
    upstream_model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_requests_created_at
    ON llm_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_requests_route
    ON llm_requests(route, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_requests_status
    ON llm_requests(status, created_at DESC);

CREATE TABLE IF NOT EXISTS llm_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES llm_requests(request_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    candidate TEXT NOT NULL,
    provider TEXT NOT NULL,
    upstream_model TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    error_code TEXT,
    error_message TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_attempts_request
    ON llm_attempts(request_id, ordinal);

CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES llm_requests(request_id) ON DELETE CASCADE,
    attempt_id INTEGER REFERENCES llm_attempts(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attributes TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trace_events_request
    ON trace_events(request_id, id);
