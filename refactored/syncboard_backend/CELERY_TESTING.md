# Celery Integration - End-to-End Testing Guide

## Overview

This guide provides step-by-step instructions for testing the complete Celery background task integration for SyncBoard 3.0 Knowledge Bank.

**What's Been Implemented:**
- ✅ Celery infrastructure (workers, tasks, job status API)
- ✅ Redis caching layer
- ✅ Background file upload processing
- ✅ Background URL/YouTube processing
- ✅ Background image OCR processing
- ✅ Frontend job polling with real-time progress
- ✅ Job status API endpoints
- ✅ Rate limiting and error handling

---

## Prerequisites

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `celery[redis]` - Task queue
- `redis` - Message broker
- `flower` - Monitoring dashboard

### 2. Start Redis

**Option A: Docker (Recommended)**
```bash
docker run -d --name syncboard-redis -p 6379:6379 redis:7-alpine
```

**Option B: Local Redis**
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server
```

**Verify Redis:**
```bash
redis-cli ping
# Should return: PONG
```

### 3. Check Environment Configuration

Verify `.env` file has Redis configuration:

```env
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Test Setup

### Terminal 1: Start FastAPI Backend

```bash
cd /home/user/project-refactored-5/project-refactored-main/project-refactored-main/refactored/syncboard_backend/backend
uvicorn main:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
✅ Database initialized
✅ Redis connected: redis://localhost:6379/0
```

**Verify API:**
```bash
curl http://localhost:8000/health
```

Should return database and Redis health status.

### Terminal 2: Start Celery Worker

**IMPORTANT:** You must specify the custom queues using the `-Q` flag. Tasks are routed to specific queues (uploads, analysis, low_priority) based on their type.

```bash
cd /home/user/project-refactored-5/project-refactored-main/project-refactored-main/refactored/syncboard_backend
# Load .env file and start worker with all queues
set -a && source .env && set +a && celery -A backend.celery_app worker --loglevel=info --concurrency=4 -Q uploads,analysis,low_priority,celery
```

**Expected Output:**
```
[tasks]
  . backend.tasks.process_file_upload
  . backend.tasks.process_url_upload
  . backend.tasks.process_image_upload
  . backend.tasks.find_duplicates_background
  . backend.tasks.generate_build_suggestions

[queues]
  . analysis         exchange=analysis(direct) key=analysis
  . celery           exchange=celery(direct) key=celery
  . low_priority     exchange=low_priority(direct) key=low_priority
  . uploads          exchange=uploads(direct) key=uploads

celery@hostname ready.
```

**Verify Worker:**
```bash
celery -A backend.celery_app inspect active
```

Should show no active tasks initially.

### Terminal 3: Start Flower Monitoring (Optional)

```bash
cd /home/user/project-refactored-5/project-refactored-main/project-refactored-main/refactored/syncboard_backend/backend
celery -A backend.celery_app flower --port=5555
```

**Access Flower:**
Open browser to: http://localhost:5555

**Flower Dashboard Shows:**
- Active workers
- Task execution times
- Success/failure rates
- Queue depths

---

## Test Cases

### Test 1: File Upload with Progress Tracking

**Objective:** Upload a PDF file and verify background processing with real-time progress.

**Steps:**

1. **Open Frontend**
   - Navigate to: http://localhost:8000
   - Login with test credentials (username: `test`, password: `test123`)

2. **Upload a Test File**
   - Go to "Upload" tab
   - Select a PDF file (or any document)
   - Click "Upload File"

3. **Expected Behavior:**
   - **Immediate Response** (<1 second):
     - Toast shows: "📤 File queued: filename.pdf"
     - File input clears
     - Button shows: "⏳ Queued..."

   - **Progress Updates** (every second):
     - Button shows: "Decoding file... 10%"
     - Button shows: "Extracting text... 25%"
     - Button shows: "AI analysis... 50%"
     - Button shows: "Clustering... 75%"
     - Button shows: "Saving... 90%"

   - **Completion** (after processing):
     - Toast shows: "✅ Uploaded! Doc 1 → Cluster 1"
     - Button resets to: "Upload File"
     - Clusters automatically refresh
     - New cluster appears with the document

4. **Verify in Terminal 2 (Celery Worker):**
   ```
   [INFO] Task backend.tasks.process_file_upload[abc123] received
   [INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Decoding file...
   [INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Extracting text...
   [INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: AI analysis...
   [INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Clustering...
   [INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Saving...
   [INFO] Task backend.tasks.process_file_upload[abc123] succeeded
   ```

5. **Verify in Flower Dashboard:**
   - Go to http://localhost:5555/tasks
   - Should see completed task with:
     - Task name: `backend.tasks.process_file_upload`
     - State: SUCCESS
     - Runtime: ~10-30 seconds
     - Result: `{doc_id: 1, cluster_id: 1, concepts: [...]}`

**Expected Result:** ✅ File processed in background, progress shown in real-time, clusters updated.

**Troubleshooting:**
- If button stays on "⏳ Queued...":
  - Check Terminal 2 for Celery worker errors
  - Check Redis is running: `redis-cli ping`
  - Check browser console for errors

- If "Processing failed" toast appears:
  - Check Terminal 2 for Python traceback
  - Verify OpenAI API key is set in `.env`
  - Check file size limits

---

### Test 2: YouTube URL Upload

**Objective:** Upload a YouTube URL and verify background transcription.

**Steps:**

1. **Open Frontend Upload Tab**

2. **Enter YouTube URL**
   - Paste a YouTube URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
   - Click "Upload URL"

3. **Expected Behavior:**
   - Toast shows: "🌐 URL queued: https://www.youtube.com/..."
   - URL input clears
   - Button shows progress:
     - "⏳ Queued..."
     - "Downloading content... 20%"
     - "AI analysis... 50%"
     - "Clustering... 75%"
     - "✅ Uploaded! Doc 2 → Cluster 2"

4. **Verify Processing Time:**
   - Should take 30-90 seconds for YouTube videos
   - Button shows progress throughout
   - User can navigate away and upload more files

**Expected Result:** ✅ YouTube URL processed in background, transcript extracted, document created.

**Note:** YouTube processing is slower (30-90s) but non-blocking. User can continue using the app.

---

### Test 3: Image Upload with OCR

**Objective:** Upload an image and verify OCR processing.

**Steps:**

1. **Prepare Test Image**
   - Use a screenshot or photo with text
   - Or create test image with text

2. **Upload Image**
   - Go to "Upload" tab
   - Select image file
   - Add optional description
   - Click "Upload Image"

3. **Expected Behavior:**
   - Toast shows: "📸 Image queued: image.png"
   - Button shows:
     - "⏳ Queued..."
     - "Decoding image... 10%"
     - "Running OCR... 30%"
     - "AI analysis... 60%"
     - "✅ Processing complete!"

4. **Verify OCR Results:**
   - Check clusters for new "Images" cluster
   - Click cluster to view document
   - Should see extracted text from image

**Expected Result:** ✅ Image processed with OCR, text extracted, document created.

---

### Test 4: Concurrent Uploads

**Objective:** Upload multiple files simultaneously to verify parallel processing.

**Steps:**

1. **Queue Multiple Files**
   - Upload 3-5 different files in quick succession
   - Don't wait for first file to complete

2. **Expected Behavior:**
   - All files queue immediately
   - Multiple toasts appear: "📤 File queued: ..."
   - Each button shows independent progress
   - Celery workers process in parallel (up to 4 concurrently)

3. **Verify in Flower:**
   - Should see multiple tasks running simultaneously
   - Tasks should complete within similar timeframes

**Expected Result:** ✅ Multiple files process in parallel, no blocking.

**Performance:**
- Before Celery: Upload file 1, wait 30s, upload file 2, wait 30s... (serial)
- After Celery: Upload files 1-5 instantly, all process simultaneously (parallel)

---

### Test 5: Error Handling

**Objective:** Verify graceful error handling for failed uploads.

**Test 5A: Invalid File**
1. Upload a corrupt or empty file
2. **Expected:** Toast shows: "❌ Processing failed: [error message]"

**Test 5B: File Too Large**
1. Upload a file >50MB
2. **Expected:** Immediate error: "File too large. Maximum size is 50MB"

**Test 5C: Rate Limiting**
1. Queue 11 files rapidly (limit is 10 concurrent jobs)
2. **Expected:** 11th file shows error: "Too many background jobs in progress"

**Test 5D: Network Interruption**
1. Upload file
2. Stop Redis: `docker stop syncboard-redis`
3. **Expected:** Frontend continues polling, eventually times out gracefully
4. Restart Redis: `docker start syncboard-redis`

**Expected Result:** ✅ All errors handled gracefully, user sees clear error messages.

---

### Test 6: Job Status API

**Objective:** Test job status endpoint directly.

**Steps:**

1. **Upload a File**
   - Note the job_id from browser network tab or logs

2. **Query Job Status via curl:**
   ```bash
   TOKEN="your-jwt-token"  # Get from browser localStorage
   JOB_ID="abc123-def456"  # Replace with actual job ID

   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8000/jobs/$JOB_ID/status
   ```

3. **Expected Response (PENDING):**
   ```json
   {
       "job_id": "abc123-def456",
       "state": "PENDING",
       "meta": {
           "message": "Task is waiting in queue...",
           "percent": 0
       },
       "result": null
   }
   ```

4. **Expected Response (PROCESSING):**
   ```json
   {
       "job_id": "abc123-def456",
       "state": "PROCESSING",
       "meta": {
           "stage": "ai_analysis",
           "message": "Running AI concept extraction...",
           "percent": 50
       },
       "result": null
   }
   ```

5. **Expected Response (SUCCESS):**
   ```json
   {
       "job_id": "abc123-def456",
       "state": "SUCCESS",
       "meta": {
           "message": "Task completed successfully",
           "percent": 100
       },
       "result": {
           "doc_id": 42,
           "cluster_id": 5,
           "concepts": [...],
           "filename": "document.pdf",
           "user_id": "test"
       }
   }
   ```

**Expected Result:** ✅ Job status API returns real-time progress.

---

## Monitoring & Debugging

### Monitor Celery Workers

**View Active Tasks:**
```bash
celery -A backend.celery_app inspect active
```

**View Worker Stats:**
```bash
celery -A backend.celery_app inspect stats
```

**View Registered Tasks:**
```bash
celery -A backend.celery_app inspect registered
```

### Monitor Redis

**Check Queue Depths:**
```bash
redis-cli llen celery
```

**Monitor Commands:**
```bash
redis-cli monitor
```

**Check Memory Usage:**
```bash
redis-cli INFO memory
```

### Browser DevTools

1. **Open Browser Console** (F12)

2. **Monitor Network Requests:**
   - Filter by "jobs" to see polling requests
   - Should see `/jobs/{job_id}/status` every second
   - Status should progress: PENDING → PROCESSING → SUCCESS

3. **Check for Errors:**
   - Console should show no errors
   - Network tab should show no 5xx errors

### Flower Dashboard

**Access:** http://localhost:5555

**Key Metrics:**
- **Tasks Tab:** View all task history
- **Workers Tab:** View worker health and concurrency
- **Monitor Tab:** Real-time task stream
- **Broker Tab:** Redis connection status

---

## Performance Benchmarks

### Before Celery (Synchronous):

| Operation | Response Time | User Experience |
|-----------|---------------|-----------------|
| Upload PDF | 30-60 seconds | Blocks, no feedback |
| Upload YouTube | 60-180 seconds | Timeouts common |
| Upload Image | 10-30 seconds | Blocks |
| Concurrent uploads | Not possible | Must wait for each |

### After Celery (Asynchronous):

| Operation | Response Time | User Experience |
|-----------|---------------|-----------------|
| Upload PDF | <1 second | Instant queue, progress shown |
| Upload YouTube | <1 second | Instant queue, progress shown |
| Upload Image | <1 second | Instant queue, progress shown |
| Concurrent uploads | <1 second each | All queue instantly, parallel processing |

**Improvement:** 30-180x faster perceived performance!

---

## Common Issues & Solutions

### Issue 1: "Job timeout - check back later"

**Cause:** Worker crashed or task taking >5 minutes

**Solution:**
1. Check Celery worker logs for errors
2. Restart worker: `Ctrl+C` then restart command
3. Increase timeout in `app.js` (pollInterval)

### Issue 2: Button stuck on "⏳ Queued..."

**Cause:** Worker not picking up jobs

**Solution:**
1. Verify worker is running: `celery -A backend.celery_app inspect active`
2. Check Redis: `redis-cli ping`
3. Restart worker

### Issue 3: "Failed to check job status"

**Cause:** Backend not responding or authentication expired

**Solution:**
1. Refresh page to renew JWT token
2. Check FastAPI backend is running
3. Verify `/jobs/{job_id}/status` endpoint exists

### Issue 4: Tasks not appearing in Flower

**Cause:** Flower not connected to same Redis instance

**Solution:**
1. Verify Flower command uses correct `backend.celery_app`
2. Check Redis URL in `.env`
3. Restart Flower

---

## Success Criteria

### All Tests Pass When:

✅ **File Upload:**
- File queues in <1 second
- Progress updates appear on button
- Success toast shows doc_id and cluster_id
- Clusters refresh automatically

✅ **URL Upload:**
- URL queues in <1 second
- Progress updates appear
- YouTube transcripts extracted
- Document created successfully

✅ **Image Upload:**
- Image queues in <1 second
- OCR processing completes
- Text extracted and searchable

✅ **Concurrent Uploads:**
- Multiple files queue simultaneously
- Each shows independent progress
- All complete successfully

✅ **Error Handling:**
- Invalid files show error messages
- Rate limiting works (max 10 jobs)
- Timeouts handled gracefully

✅ **Monitoring:**
- Flower dashboard shows tasks
- Worker logs show progress
- Redis stores job results

---

## Next Steps After Testing

1. **Document any issues found**
2. **Measure actual performance improvement**
3. **Test with production-like load (50+ files)**
4. **Configure production deployment:**
   - Docker Compose setup
   - systemd services for workers
   - Redis persistence
   - Monitoring alerts

5. **Optional enhancements:**
   - Server-Sent Events (SSE) for push notifications
   - Batch upload UI (select multiple files at once)
   - Job history page (view past uploads)
   - Analytics caching with Redis

---

**Last Updated:** 2025-11-16
**Version:** 1.0 (Complete Celery Integration)
