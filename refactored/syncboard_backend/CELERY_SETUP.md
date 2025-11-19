# Celery Background Task Queue - Setup Guide

## Overview

SyncBoard 3.0 now uses **Celery** for background task processing to handle long-running operations without blocking the API:

- **File uploads** (PDF, audio, video, images) - 30-120 seconds
- **YouTube/URL ingestion** - 60-180 seconds
- **Duplicate detection** - O(n²) complexity
- **Build suggestions** - 15-45 seconds of AI analysis
- **Analytics caching** - for faster dashboard loads

### Architecture

```
┌─────────────┐
│   FastAPI   │ ← API returns job_id immediately
│   Backend   │
└──────┬──────┘
       │ Queues jobs
       ↓
┌─────────────┐
│    Redis    │ ← Message broker + result backend
└──────┬──────┘
       │ Workers poll for jobs
       ↓
┌─────────────┐
│   Celery    │ ← 2-4 concurrent workers
│   Workers   │    Process jobs in background
└─────────────┘
```

### Benefits

- ✅ **No more timeouts** - Upload returns immediately with job ID
- ✅ **Real-time progress** - Frontend polls for status updates
- ✅ **Batch uploads** - Upload multiple files simultaneously
- ✅ **Better UX** - Users can continue working while files process
- ✅ **Scalable** - Add more workers to handle higher load

---

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `celery[redis]` - Task queue with Redis support
- `redis` - Python Redis client
- `flower` - Celery monitoring dashboard

### 2. Install and Start Redis

#### Option A: Docker (Recommended)

```bash
# Start Redis container
docker run -d --name syncboard-redis -p 6379:6379 redis:7-alpine

# Verify Redis is running
docker ps | grep redis
```

#### Option B: Local Installation

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Windows:**
- Download from: https://redis.io/download
- Or use Docker Desktop

#### Verify Redis Connection

```bash
redis-cli ping
# Should return: PONG
```

### 3. Configure Environment Variables

Edit `.env` file (already configured in this project):

```env
# Redis connection URL
REDIS_URL=redis://localhost:6379/0

# Celery broker and result backend
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

For Docker deployment:
```env
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

---

## Running Celery Workers

### Development Mode

**Terminal 1 - Start FastAPI Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Start Celery Worker:**
```bash
cd backend
celery -A backend.celery_app worker --loglevel=info --concurrency=4
```

**Terminal 3 - Start Flower Monitoring (Optional):**
```bash
cd backend
celery -A backend.celery_app flower --port=5555
```

Access Flower dashboard at: http://localhost:5555

### Production Mode

**Using systemd (Linux):**

Create `/etc/systemd/system/syncboard-celery.service`:

```ini
[Unit]
Description=SyncBoard Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=syncboard
Group=syncboard
WorkingDirectory=/opt/syncboard/backend
Environment="PATH=/opt/syncboard/venv/bin"
ExecStart=/opt/syncboard/venv/bin/celery -A backend.celery_app worker \
          --loglevel=info \
          --concurrency=4 \
          --pidfile=/var/run/celery/syncboard.pid \
          --logfile=/var/log/celery/syncboard.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl start syncboard-celery
sudo systemctl enable syncboard-celery
sudo systemctl status syncboard-celery
```

**Using Docker Compose:**

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - db

  celery_worker:
    build: .
    command: celery -A backend.celery_app worker --loglevel=info --concurrency=4
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - backend

  flower:
    build: .
    command: celery -A backend.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis
      - celery_worker

volumes:
  redis_data:
```

---

## Worker Configuration

### Concurrency

Number of worker processes that handle tasks simultaneously:

```bash
# Low traffic (default)
celery -A backend.celery_app worker --concurrency=2

# Medium traffic
celery -A backend.celery_app worker --concurrency=4

# High traffic
celery -A backend.celery_app worker --concurrency=8
```

**Rule of thumb:** `concurrency = 2 * CPU_cores`

### Task Queues

Tasks are automatically routed to specialized queues:

| Queue | Tasks | Priority |
|-------|-------|----------|
| `uploads` | File/URL uploads, image processing | High |
| `analysis` | Duplicate detection, build suggestions | Medium |
| `low_priority` | Analytics caching | Low |

Start workers for specific queues:

```bash
# Worker for upload tasks only (high priority)
celery -A backend.celery_app worker --queues=uploads --concurrency=4

# Worker for analysis tasks
celery -A backend.celery_app worker --queues=analysis --concurrency=2

# Worker for all queues
celery -A backend.celery_app worker --queues=uploads,analysis,low_priority
```

### Autoscaling

Workers automatically scale based on load:

```bash
celery -A backend.celery_app worker --autoscale=10,3
# Min 3 workers, max 10 workers
```

---

## Monitoring

### Flower Dashboard

Start Flower:
```bash
celery -A backend.celery_app flower --port=5555
```

Access at: http://localhost:5555

Features:
- Real-time task monitoring
- Worker status and performance
- Task success/failure rates
- Task execution times
- Queue depths

### Command-Line Monitoring

**Check worker status:**
```bash
celery -A backend.celery_app status
```

**Inspect active tasks:**
```bash
celery -A backend.celery_app inspect active
```

**Inspect registered tasks:**
```bash
celery -A backend.celery_app inspect registered
```

**Monitor task stats:**
```bash
celery -A backend.celery_app inspect stats
```

**View task history:**
```bash
celery -A backend.celery_app events
```

### Logs

Worker logs include progress for each task:

```
[INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Decoding file...
[INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Extracting text...
[INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: AI analysis...
[INFO] Task backend.tasks.process_file_upload[abc123] - PROCESSING: Clustering...
[INFO] Task backend.tasks.process_file_upload[abc123] - SUCCESS: doc_id=42, cluster_id=5
```

---

## Troubleshooting

### Redis Connection Failed

**Error:** `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# If not running, start Redis
# Docker:
docker start syncboard-redis

# macOS:
brew services start redis

# Linux:
sudo systemctl start redis-server
```

### Tasks Not Executing

**Issue:** Tasks queued but not processing

**Solution:**
```bash
# 1. Check if workers are running
celery -A backend.celery_app inspect active

# 2. Restart workers
# Kill workers:
pkill -f 'celery worker'

# Start workers:
celery -A backend.celery_app worker --loglevel=info --concurrency=4
```

### Task Stuck in PENDING

**Issue:** Job status shows "PENDING" forever

**Possible causes:**
1. Worker not running
2. Task name mismatch
3. Worker doesn't have task module loaded

**Solution:**
```bash
# Check registered tasks
celery -A backend.celery_app inspect registered

# Should show:
# - backend.tasks.process_file_upload
# - backend.tasks.process_url_upload
# - backend.tasks.process_image_upload
# - backend.tasks.find_duplicates_background
# - backend.tasks.generate_build_suggestions

# Restart worker with correct module path
celery -A backend.celery_app worker --loglevel=debug
```

### High Memory Usage

**Issue:** Workers consuming too much RAM

**Solution:**
```bash
# Set max tasks per worker before restart
celery -A backend.celery_app worker --max-tasks-per-child=100

# Or in celery_app.py:
worker_max_tasks_per_child = 100  # Restart worker after 100 tasks
```

### Task Timeout

**Issue:** Tasks fail with "SoftTimeLimitExceeded"

**Current limits:**
- Soft limit: 9 minutes (allows cleanup)
- Hard limit: 10 minutes (force kill)

**Solution:**
```bash
# Increase timeout in celery_app.py:
task_time_limit = 1200  # 20 minutes hard limit
task_soft_time_limit = 1080  # 18 minutes soft limit

# Restart worker
```

---

## API Usage

### Upload File with Background Processing

**Frontend:**
```javascript
// Upload file - returns job_id immediately
const uploadFile = async (file) => {
    const base64Content = await fileToBase64(file);

    const response = await fetch('/upload_file', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            filename: file.name,
            content: base64Content
        })
    });

    const { job_id } = await response.json();

    // Poll for status
    pollJobStatus(job_id);
};

const pollJobStatus = (jobId) => {
    const interval = setInterval(async () => {
        const response = await fetch(`/jobs/${jobId}/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const { state, meta, result } = await response.json();

        if (state === 'PROCESSING') {
            // Show progress: "AI analysis... 50%"
            showProgress(meta.message, meta.percent);
        }
        else if (state === 'SUCCESS') {
            clearInterval(interval);
            showToast(`Uploaded! Doc ${result.doc_id} → Cluster ${result.cluster_id}`);
            refreshDocuments();
        }
        else if (state === 'FAILURE') {
            clearInterval(interval);
            showToast(`Upload failed: ${meta.error}`, 'error');
        }
    }, 1000); // Poll every second
};
```

**Backend Response (Immediate):**
```json
{
    "job_id": "abc123-def456-ghi789"
}
```

**Progress Updates (Polling /jobs/{job_id}/status):**
```json
{
    "job_id": "abc123-def456-ghi789",
    "state": "PROCESSING",
    "meta": {
        "stage": "ai_analysis",
        "message": "Running AI concept extraction...",
        "percent": 50
    },
    "result": null
}
```

**Success Result:**
```json
{
    "job_id": "abc123-def456-ghi789",
    "state": "SUCCESS",
    "meta": {
        "message": "Task completed successfully",
        "percent": 100
    },
    "result": {
        "doc_id": 42,
        "cluster_id": 5,
        "concepts": [...],
        "filename": "document.pdf"
    }
}
```

---

## Performance Tuning

### Redis Configuration

Edit `/etc/redis/redis.conf`:

```conf
# Memory limit
maxmemory 2gb
maxmemory-policy allkeys-lru  # Evict least recently used keys

# Persistence (optional - can disable for better performance)
save ""  # Disable RDB snapshots for pure cache usage

# Connections
maxclients 10000
```

### Worker Pool Types

```bash
# Prefork (default) - Good for CPU-bound tasks
celery -A backend.celery_app worker --pool=prefork --concurrency=4

# Gevent - Good for I/O-bound tasks (file processing, API calls)
celery -A backend.celery_app worker --pool=gevent --concurrency=100

# Threading - Lighter than prefork
celery -A backend.celery_app worker --pool=threads --concurrency=10
```

**Recommendation:** Use `prefork` for AI tasks (concept extraction, clustering) and `gevent` for file downloads.

---

## Next Steps

1. **Test the integration:**
   ```bash
   # Terminal 1: Start Redis
   docker run -d --name syncboard-redis -p 6379:6379 redis:7-alpine

   # Terminal 2: Start backend
   cd backend
   uvicorn main:app --reload

   # Terminal 3: Start Celery worker
   celery -A backend.celery_app worker --loglevel=info --concurrency=4

   # Terminal 4: Start Flower monitoring
   celery -A backend.celery_app flower --port=5555
   ```

2. **Upload a test file** via frontend and watch progress in:
   - Backend logs (FastAPI)
   - Worker logs (Celery)
   - Flower dashboard (http://localhost:5555)

3. **Monitor performance:**
   - Check task execution times in Flower
   - Monitor Redis memory usage: `redis-cli INFO memory`
   - Monitor worker CPU/RAM: `top` or `htop`

4. **Scale as needed:**
   - Add more workers for higher throughput
   - Use multiple queues for task prioritization
   - Deploy Redis Sentinel for high availability

---

## Additional Resources

- **Celery Documentation:** https://docs.celeryproject.org/
- **Flower Documentation:** https://flower.readthedocs.io/
- **Redis Documentation:** https://redis.io/documentation
- **FastAPI + Celery Guide:** https://fastapi.tiangolo.com/deployment/

---

**Last Updated:** 2025-11-16 (Phase 2: Celery Integration)
