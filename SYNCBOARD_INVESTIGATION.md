# SyncBoard Troubleshooting Investigation - 2025-11-19

## Scope
- Read TROUBLESHOOTING_GUIDE.md and inspected current frontend/backend implementation without modifying code.
- Focused on upload UX, Celery task handling, KB document counts, and logging behavior noted in the guide.

## Findings

### 1. Frontend job polling schema mismatch
- uploadUrl, uploadFile, and uploadImage already enqueue background jobs and immediately return (syncboard_backend/backend/static/app.js:203-323).
- pollJobStatus expects /jobs/{id}/status to return {state, meta, result} and only clears the interval when state === 'SUCCESS' (syncboard_backend/backend/static/app.js:2425-2485).
- The FastAPI jobs router returns {job_id, status, progress, ...doc_id...} with no state, meta, or nested esult (syncboard_backend/backend/routers/jobs.py:97-135).
- Because state is always undefined, uploads appear to "timeout" on the frontend after 5 minutes even though the corresponding Celery task saved data successfully.

### 2. KB document_count only updates for synchronous text uploads
- The text upload endpoint increments DBKnowledgeBase.document_count after persisting (syncboard_backend/backend/routers/uploads.py:185-203).
- Celery tasks for URL/file/image uploads (process_url_upload, process_file_upload, process_image_upload) save documents but never adjust document_count before returning (syncboard_backend/backend/tasks.py:297, 448, 614).
- Result: counts remain stale until manually corrected in SQL, matching the symptom described in the troubleshooting guide.

### 3. Celery worker startup logs look like ongoing processing
- Every worker process logs "Initializing Celery worker cache from database" inside worker_process_init (syncboard_backend/backend/tasks.py:138-149).
- There is no [STARTUP] vs [TASK] prefix, so when the pool respawns it resembles active upload work even if no tasks are running.

### 4. Transcription speed is unchanged; additional steps are expected
- Large YouTube/audio uploads are compressed and chunked before Whisper transcription (syncboard_backend/backend/ingest.py:102-151, 227-286).
- Extra log lines for compression and chunk-by-chunk transcription increase perceived duration, but throughput matches the previous implementation.

## Suggested Next Actions
1. Align pollJobStatus with the API response (or update /jobs/{id}/status to emit the state/meta/result shape) so the frontend surfaces real progress instead of triggering the generic timeout toast.
2. After Celery tasks persist new docs, increment DBKnowledgeBase.document_count in the database to keep counts accurate for all ingestion paths.
3. Tag worker-init logs with a [STARTUP] prefix (and optionally tag task logs with [TASK]) to distinguish harmless worker churn from active processing in log streams.
4. Communicate that multi-minute YouTube uploads are expected due to Whisper chunking, and keep the informational toast about 30–120s processing to set user expectations.
