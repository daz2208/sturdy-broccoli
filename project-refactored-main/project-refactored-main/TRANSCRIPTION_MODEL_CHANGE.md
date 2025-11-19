# Transcription Model Change - November 17, 2025

## Changes Made

### Model Switch: whisper-1 → gpt-4o-mini-transcribe

**Files Modified:**
- `backend/ingest.py` - Added `TRANSCRIPTION_MODEL` environment variable (line 37)
- `backend/ingest.py` - Replaced all 4 hardcoded `model="whisper-1"` with `model=TRANSCRIPTION_MODEL` (lines 251, 302, 398, 707)
- `docker-compose.yml` - Added `TRANSCRIPTION_MODEL` env var to backend service (line 75)
- `docker-compose.yml` - Added `TRANSCRIPTION_MODEL` env var to celery service (line 130)
- `docker-compose.yml` - Added `TRANSCRIPTION_MODEL` env var to celery-worker-2 service (line 169)

**Default Model:** `gpt-4o-mini-transcribe`

**Environment Variable:**
```bash
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

### Performance Improvement

**Old Model (whisper-1):**
- Timed out after 10 minutes on 15-minute video
- Failed to complete transcription
- Process killed by Celery hard timeout

**New Model (gpt-4o-mini-transcribe):**
- Completed in 42 seconds for 14-minute video
- 13x faster than timeout
- Successfully returned transcript

---

## Current Issue: Incomplete Transcriptions

### Problem
YouTube video transcripts are being cut off mid-sentence.

**Example:**
- Video: "How I Sold These 4 AI Agents for $23,000" (14 minutes, 858 seconds)
- Audio size: 19.64MB (under 25MB limit, no compression)
- Transcription time: 42 seconds
- **Transcript length: 9,913 characters** ⚠️
- **Transcript ends:** "...actually gives you more things to manage, more moving pieces, and more"

### Evidence
- Celery log: `Successfully transcribed 9913 characters`
- Database content: 10,122 characters (9,913 + metadata)
- Transcript cuts off mid-sentence
- 14-minute video should produce ~15,000-20,000 characters

### Root Cause Analysis

**Possible causes:**
1. **Model token limits** - `gpt-4o-mini-transcribe` may have lower output token limits than `whisper-1`
2. **Audio quality** - Compression or audio quality issues causing model to stop
3. **API response truncation** - OpenAI API truncating long responses
4. **Silence detection** - Model stopping at long pauses/music sections
5. **Undocumented model differences** - `gpt-4o-mini-transcribe` behavior differs from `whisper-1`

---

## Recommended Fixes (Priority Order)

### Option 1: Force Audio Chunking (Recommended)
**Strategy:** Split all audio files into smaller chunks regardless of size

**Implementation:**
- Modify `ingest.py` to chunk by duration (5-minute segments) instead of file size
- Process each chunk separately
- Concatenate results
- Ensures no single transcription exceeds model limits

**Benefits:**
- Guarantees complete transcription
- Works around any model token limits
- More robust for long videos

**Files to modify:**
```python
# backend/ingest.py
# Add duration-based chunking before line 242
if video_duration > 300:  # 5 minutes
    chunks = chunk_audio_by_duration(audio_path, chunk_duration=300)
    transcripts = [transcribe_chunk(c) for c in chunks]
    return concatenate_transcripts(transcripts)
```

### Option 2: Switch Back to whisper-1
**Strategy:** Revert to original model and increase timeout

**Implementation:**
```bash
# .env or docker-compose.yml
TRANSCRIPTION_MODEL=whisper-1
```

**In celery_app.py:**
```python
task_time_limit=1200   # 20 minutes instead of 10
task_soft_time_limit=1080  # 18 minutes
```

**Trade-offs:**
- Slower (2-5 minutes per video vs 40 seconds)
- Higher cost (whisper-1 more expensive)
- More reliable for long content
- Proven track record

### Option 3: Hybrid Approach
**Strategy:** Use `gpt-4o-mini-transcribe` with fallback

**Implementation:**
```python
try:
    transcript = transcribe_with_model("gpt-4o-mini-transcribe")
    if len(transcript) < expected_minimum:
        logger.warning("Short transcript detected, retrying with whisper-1")
        transcript = transcribe_with_model("whisper-1")
except TimeoutError:
    transcript = transcribe_with_chunks()
```

**Benefits:**
- Fast when it works
- Reliable fallback
- Adaptive to different scenarios

### Option 4: Add max_tokens Parameter
**Strategy:** Explicitly set higher output limits

**Implementation:**
```python
# backend/ingest.py - in transcription calls
transcript = client.audio.transcriptions.create(
    model=TRANSCRIPTION_MODEL,
    file=audio_file,
    response_format="text",
    max_tokens=16000  # Add explicit limit
)
```

**Note:** May not be supported by audio transcription endpoint

### Option 5: Investigate Model Behavior
**Strategy:** Test and document model differences

**Steps:**
1. Test same video with both models
2. Compare output lengths
3. Check for consistent cutoff points
4. Contact OpenAI support about model limits
5. Document findings and update accordingly

---

## Additional Improvements Made

### Auto-Reload from Database
**Problem:** Backend required manual restart to see new documents

**Solution:** Added Redis pub/sub notifications
- Celery publishes "data_changed" after saving
- Backend subscribes and auto-reloads from database
- No more manual restarts needed

**Files modified:**
- `backend/redis_client.py` - Added `notify_data_changed()`
- `backend/tasks.py` - Calls notification after saves
- `backend/main.py` - Background listener thread

### Second Celery Worker
**Added:** `celery-worker-2` service in docker-compose.yml
- Enables parallel video transcriptions
- 2 videos can process simultaneously
- Better resource utilization

---

## Testing Recommendations

### Before Production Deployment:

1. **Test with various video lengths:**
   - Short (2-3 minutes)
   - Medium (10-15 minutes)
   - Long (30+ minutes)

2. **Compare models:**
   - Same video with `whisper-1`
   - Same video with `gpt-4o-mini-transcribe`
   - Document output differences

3. **Verify chunking works:**
   - Test audio > 25MB (triggers compression)
   - Test audio > 25MB after compression (should trigger chunking)
   - Verify chunks concatenate correctly

4. **Monitor costs:**
   - Track OpenAI API usage
   - Compare costs between models
   - Optimize based on usage patterns

---

## Configuration Guide

### To Use gpt-4o-mini-transcribe (Current):
```bash
# .env file
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

### To Switch Back to whisper-1:
```bash
# .env file
TRANSCRIPTION_MODEL=whisper-1
```

### To Use Custom Model:
```bash
# .env file
TRANSCRIPTION_MODEL=your-model-name
```

**Apply changes:**
```bash
docker-compose down
docker-compose up -d
```

---

## Monitoring

### Check Transcription Logs:
```bash
docker-compose logs celery | grep -i "transcrib"
```

### Check for Timeouts:
```bash
docker-compose logs celery | grep -i "timeout\|limit"
```

### Verify Complete Transcriptions:
```bash
docker-compose exec db psql -U syncboard -d syncboard -c \
  "SELECT doc_id, length(content), RIGHT(content, 50) FROM vector_documents;"
```

---

## Status: REQUIRES ACTION

**Current state:** ⚠️ Transcriptions completing but **truncated**

**Immediate action needed:** Implement Option 1 (Force Audio Chunking) or Option 2 (Switch back to whisper-1)

**Timeline:** Should be addressed before processing more long-form content

**Owner:** Development team

---

**Last Updated:** 2025-11-17
**Updated By:** Claude (Session fixing previous Claude's mess)
**Next Review:** After implementing chosen fix
