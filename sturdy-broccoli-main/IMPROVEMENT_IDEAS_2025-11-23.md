## Near-term improvements

- **Celery safety rails**: Add per-task soft/hard timeouts and a simple circuit-breaker for repeated failures. Expose `max_tasks_per_child` and `worker_concurrency` via env to tune quickly without rebuilds.
- **Upload backpressure**: Cap concurrent uploads per user and surface queue depth in the frontend; return a “queued” state with periodic status updates instead of keeping long polls open.
- **Zip ingestion guardrails**: Add a size-based short-circuit (e.g., >200MB → require user confirmation) and log per-archive stats (file count, nested zips, bytes) to a dedicated metric for alerting.
- **Sampling diagnostics**: Emit a concise ingestion summary (docs, tokens, OpenAI calls, elapsed) to logs and optionally to a “job report” API the frontend can show on completion/error.
- **Retry strategy**: Distinguish between transient errors (retry with jitter) and deterministic ones (no retry); cap retries per job and surface failure reasons back to the UI.

## Performance and cost

- **Chunking budgets**: Enforce tighter caps for embeddings/summaries per document (e.g., size buckets) and bail early with a user-facing message when limits are hit.
- **Batching**: Where possible, batch small text fragments for embeddings to reduce call count; cache embeddings for identical content hashes.
- **Concurrency shaping**: Use a semaphore around OpenAI calls to prevent bursty fan-out; expose limits via env and meter per-user tokens to avoid noisy-neighbor effects.

## Observability

- **Job traces**: Add structured logs per job id with phases (upload, unzip, chunk, embed, summarize) and durations; ship to a single sink (stdout is fine) with JSON lines.
- **Dashboards**: Track queue depth, active tasks, task durations, failure reasons, and OpenAI usage (calls/tokens) with a lightweight dashboard (e.g., Grafana + Prometheus or even a simple HTML status page backed by Redis metrics).
- **Alerting**: Set thresholds for task duration and error rate; alert when exceeded (even a basic email/webhook).

## Reliability and safety

- **Input validation**: Harden MIME/type checks and reject obviously harmful or unsupported archives early; surface clear reasons to the user.
- **Resource caps**: Limit per-job temp disk usage and memory for unzip; fail fast with a helpful message when caps are exceeded.
- **Idempotency**: Use a job token/hash to avoid reprocessing identical uploads if the user resubmits.

## Developer experience

- **Test matrix**: Ensure PYTHONPATH is set in test runner scripts to avoid import errors; keep ingestion tests runnable with clear targets.
- **Local profiles**: Provide a `docker-compose.override.yml` example with lower concurrency and fake OpenAI for dev speed; include a `make test-ingest` convenience target.
- **Docs**: Brief “operating guide” for starting/stopping workers, clearing queues, and reading job status endpoints; include a troubleshooting section for stuck uploads.
