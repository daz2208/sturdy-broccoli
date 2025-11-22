# SyncBoard KB System - Issues to Fix

## The Real Issues User Is Experiencing

### Issue 1: Upload Hangs Then Shows Error ⚠️ HIGH PRIORITY

**Symptoms:**
- User uploads YouTube URL via frontend
- Upload appears to hang/freeze
- Shows "couldn't complete" error
- **BUT backend logs show task succeeded** (118s, saved to DB)

**Root Cause:**
Frontend timeout is too short. Backend takes 1-2 min for video transcription, frontend gives up before backend finishes.

**What's Happening:**
1. User submits URL
2. Backend queues Celery task
3. Task processes (download → transcribe → extract → save)
4. Frontend times out waiting (probably 30-60s timeout)
5. Task actually completes successfully after frontend gave up
6. User thinks it failed, but doc is in database

**Files to Check:**
- `app.js` - Look for fetch/axios timeout settings on upload requests
- `routers/uploads.py` - Check if endpoint waits for task completion or returns immediately

**Expected Fix:**
Upload should be async:
```python
# Return immediately with task ID
task = process_url_upload.delay(url, kb_id, user_id)
return {"task_id": task.id, "status": "processing"}

# Frontend polls separate endpoint:
GET /tasks/{task_id} → {"status": "processing|completed|failed", "progress": 60}
```

---

### Issue 2: Storage/Processing After Upload Completes ⚠️ MEDIUM PRIORITY

**Symptoms:**
- Upload finishes (transcribe done, doc saved)
- Celery workers keep showing activity
- Logs show "Initializing cache from database" messages
- Process doesn't cleanly stop

**What User Sees:**
```
[ForkPoolWorker-15] Initializing Celery worker cache from database
[ForkPoolWorker-15] Loaded from database: 1 documents in 1 KBs, 1 clusters, 2 users
[ForkPoolWorker-1] Initializing Celery worker cache from database
[ForkPoolWorker-1] Loaded from database: 1 documents in 1 KBs, 1 clusters, 2 users
...continues for many workers...
```

**Root Cause:**
This is **normal Celery behavior** - workers load cache on startup. NOT related to the upload.

**Actual Issue:**
Logging makes it LOOK like upload is still processing when it's just workers initializing their cache. This happens on worker pool startup, not during tasks.

**Files to Check:**
- `tasks.py` or `main.py` - Look for cache initialization code
- Add log prefixes to distinguish: `[STARTUP]` vs `[TASK]`

**Expected Fix:**
Better logging:
```python
logger.info("[STARTUP] Initializing worker cache from database")
# vs
logger.info("[TASK] Processing upload for doc_id {doc_id}")
```

---

### Issue 3: "Slower" Transcription (NOT ACTUALLY AN ISSUE) ✅

**Symptoms:**
User reports same video takes longer with new version.

**Reality:**
Transcription is **same speed**. Perceived slowness due to:
1. Better logging shows each chunk (looks like more steps)
2. Video chunking for large files (correct behavior - prevents Whisper 25MB limit)
3. More verbose progress updates

**Logs show it's working correctly:**
```
Downloaded: From Zero to RAG Agent (1359s, 31.12MB)
Audio file (31.12MB) exceeds Whisper limit (25MB). Compressing...
Compressed audio: 31.12MB → 10.37MB (66.7% reduction)
Video duration exceeds chunk threshold. Splitting into 300-second segments...
Split audio into 5 chunks
Transcribing chunk 1/5...
Transcribing chunk 2/5...
...
Successfully transcribed 29572 characters from 5 chunks
```

**This is working as designed.** NO FIX NEEDED.

---

## Storage Architecture Status ✅ WORKING

Nested dict structure verified via SQL:
```python
documents[kb_id][doc_id] = content  # ✅ Correct
metadata[kb_id][doc_id] = meta     # ✅ Correct  
clusters[kb_id][cluster_id] = cluster  # ✅ Correct
```

Database verification:
- 2 documents with correct `knowledge_base_id: fdb42d38...`
- 2 clusters with correct `knowledge_base_id: fdb42d38...`
- All data properly scoped by KB

**NO STORAGE ISSUES FOUND.**

---

## Minor Issue: Document Count Not Auto-Updating

KB showed `document_count: 0` even though 2 docs existed. Fixed with manual UPDATE.

**Files to Check:**
- `tasks.py` - After saving document, should increment KB count
- `db_repository.py` - Document save method
- `routers/uploads.py` - After task completes

**Expected code somewhere:**
```python
# After document saved
db.query(DBKnowledgeBase).filter(
    DBKnowledgeBase.id == kb_id
).update({
    DBKnowledgeBase.document_count: DBKnowledgeBase.document_count + 1
})
db.commit()
```

---

## Summary for Claude Code

**Fix These:**
1. Make upload endpoint async (return task ID immediately)
2. Add task status polling endpoint
3. Increment KB document_count after doc save
4. Improve logging (add STARTUP vs TASK prefixes)

**Don't Touch:**
- Transcription chunking (working correctly)
- Storage structure (working correctly)
- Cache initialization (normal behavior)

**Test After Fixes:**
1. Upload YouTube URL → should return immediately with task_id
2. Frontend polls /tasks/{id} for status
3. After completion, KB document_count should auto-increment
4. Logs should clearly show STARTUP vs TASK operations
