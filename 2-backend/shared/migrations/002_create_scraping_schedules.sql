CREATE TABLE IF NOT EXISTS public.scraping_schedules (
    id                  UUID PRIMARY KEY,
    name                TEXT NOT NULL,
    platform            TEXT NOT NULL,
    resource_type       TEXT NOT NULL,
    cron_expression     TEXT NOT NULL,
    timezone            TEXT NOT NULL,
    request_payload     JSONB NOT NULL,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at         TIMESTAMPTZ,
    last_started_at     TIMESTAMPTZ,
    last_finished_at    TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_status         TEXT,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_scraping_schedules_due
ON public.scraping_schedules (enabled, next_run_at);
