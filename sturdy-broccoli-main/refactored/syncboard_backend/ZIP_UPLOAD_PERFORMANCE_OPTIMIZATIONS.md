# ZIP Upload Performance Optimizations

**Date:** 2025-11-28
**Status:** NEEDS IMPLEMENTATION
**Priority:** HIGH
**Current Performance:** 23 minutes for 29 files (~47 seconds per file)
**Target Performance:** < 5 minutes for 29 files (~10 seconds per file)

---

## 🚨 Current Bottleneck Analysis

### Performance Breakdown (Per File):
1. ✅ Extract from ZIP: < 0.1s (FAST)
2. ✅ Parse content: < 0.5s (FAST)
3. ⚠️ **OpenAI concept extraction: 2-5s (SLOW - PRIMARY BOTTLENECK)**
4. ⚠️ **OpenAI embeddings generation: 1-2s (SLOW - SECONDARY BOTTLENECK)**
5. ✅ Clustering calculation: < 0.5s (FAST)
6. ✅ Database save: < 0.2s (FAST)

**Total per file:** 4-8 seconds of AI API calls + 1-2 seconds overhead = 5-10s per file

### Current ZIP Processing:
- **Test case:** 29 files (7 readme.md + 22 JSON files)
- **Time taken:** 23 minutes
- **Celery workers:** 6 parallel workers
- **Issue:** Sequential API calls + rate limiting + network latency

---

## 📋 Optimization Strategies (Ordered by Impact)

### 1. Smart File Filtering - Skip Concept Extraction for Low-Value Files
**Impact:** HIGH (30-50% speed improvement)
**Effort:** LOW
**Implementation Time:** 30 minutes

**Problem:**
- Processing readme.md files (7 in test ZIP)
- Small files with minimal content
- Duplicate/similar files

**Solution:**
Skip concept extraction for:
- Files < 500 characters (not worth the API cost)
- readme.md, LICENSE, .gitignore (metadata files)
- Duplicate content (hash check before processing)

**Files to modify:**
```
backend/tasks.py (process_file_upload function)
backend/ingest.py (add skip_concept_extraction flag)
```

**Implementation:**
```python
# In backend/tasks.py - before concept extraction

# Skip concept extraction for small/metadata files
SKIP_CONCEPT_FILES = {
    'readme.md', 'readme.txt', 'license', 'license.txt',
    '.gitignore', '.dockerignore', 'changelog.md'
}

filename_lower = filename.lower()
content_length = len(content)

skip_concepts = (
    content_length < 500 or
    filename_lower in SKIP_CONCEPT_FILES or
    any(filename_lower.endswith(ext) for ext in ['.md', '.txt'] if content_length < 2000)
)

if skip_concepts:
    # Use default/minimal concepts
    concepts = [{'name': 'document', 'category': 'concept', 'confidence': 0.5}]
    logger.info(f"Skipped concept extraction for {filename} (small/metadata file)")
else:
    # Normal concept extraction
    concepts = await concept_extractor.extract(content)
```

**Expected Result:**
- 7 files (readme.md) × 3s saved = **21 seconds saved**
- Fewer OpenAI API calls = lower costs

---

### 2. Batch Embeddings Generation
**Impact:** HIGH (40-60% speed improvement)
**Effort:** MEDIUM
**Implementation Time:** 1-2 hours

**Problem:**
- Each file makes a separate embeddings API call (1-2s each)
- 29 files = 29 separate API calls
- Network overhead + latency adds up

**Solution:**
Batch multiple documents into a single OpenAI embeddings call:
- OpenAI supports up to 2,048 inputs per batch
- Process 10-20 files at once

**Files to modify:**
```
backend/embedding_service.py (batch_embed function)
backend/tasks.py (collect docs before embedding)
```

**Implementation:**
```python
# In backend/tasks.py - batch embedding approach

# Option A: Accumulate files in Redis queue, batch process every 5 seconds
# Option B: Process ZIP files in batches of 10

from backend.embedding_service import EmbeddingService

embedding_service = EmbeddingService()

# Collect all extracted files from ZIP
extracted_files = []  # List of (content, metadata)

for file in zip_contents:
    content = extract_content(file)
    extracted_files.append({
        'content': content,
        'filename': file.filename,
        'doc_id': assign_doc_id()
    })

# Batch embed all files at once
contents = [f['content'] for f in extracted_files]
embeddings = await embedding_service.batch_embed(contents)

# Save all with embeddings
for i, file_data in enumerate(extracted_files):
    save_document(
        content=file_data['content'],
        embedding=embeddings[i],
        filename=file_data['filename']
    )
```

**Expected Result:**
- 29 API calls → 2-3 batch calls
- **15-20 seconds saved**
- Better API rate limit utilization

---

### 3. Parallel Processing with Multiple Queues
**Impact:** MEDIUM (20-30% speed improvement)
**Effort:** MEDIUM
**Implementation Time:** 1 hour

**Problem:**
- All files processed by same queue
- Rate limiting affects all workers
- No priority for small vs large files

**Solution:**
Create separate Celery queues:
- **Fast queue:** Small files (< 10KB)
- **Slow queue:** Large files (> 100KB)
- **AI queue:** Files requiring concept extraction

**Files to modify:**
```
backend/celery_app.py (add queue routing)
backend/tasks.py (route tasks to appropriate queue)
docker-compose.yml (configure workers per queue)
```

**Implementation:**
```python
# In backend/celery_app.py

# Queue routing
app.conf.task_routes = {
    'backend.tasks.process_file_upload': {
        'queue': 'uploads'
    },
    'backend.tasks.process_small_file': {
        'queue': 'fast'
    },
    'backend.tasks.process_large_file': {
        'queue': 'slow'
    }
}

# In backend/tasks.py - smart routing
if file_size < 10_000:
    process_small_file.apply_async(args=[...], queue='fast')
elif file_size > 100_000:
    process_large_file.apply_async(args=[...], queue='slow')
else:
    process_file_upload.apply_async(args=[...], queue='uploads')
```

**Expected Result:**
- Small files process immediately (no waiting)
- Better worker utilization
- **5-8 seconds saved on average**

---

### 4. Concept Extraction Caching (Already Implemented - Verify)
**Impact:** MEDIUM (only for duplicate content)
**Effort:** LOW
**Implementation Time:** 15 minutes (verification only)

**Current Status:**
- Redis caching enabled via `ENABLE_CONCEPT_CACHING=true`
- Cache TTL: 7 days

**Action Required:**
Verify caching is working properly:
```bash
# Check Redis for cached concepts
docker-compose exec redis redis-cli
> KEYS concept:*
> TTL concept:<some-hash>
```

**Files to verify:**
```
backend/constants.py (line 86)
backend/concept_extractor.py (cache implementation)
backend/cache.py (Redis operations)
```

**Expected Result:**
- Duplicate files use cached concepts
- **3-5 seconds saved per duplicate**

---

### 5. Async Pipeline - Stream Results to UI
**Impact:** LOW (perceived performance improvement)
**Effort:** HIGH
**Implementation Time:** 3-4 hours

**Problem:**
- User waits for all files to complete
- No feedback during processing
- Feels slow even if fast

**Solution:**
Stream results as files complete:
- WebSocket updates for each file
- Show progress bar (X of Y files complete)
- Display completed files immediately

**Files to modify:**
```
backend/tasks.py (emit WebSocket events)
backend/routers/uploads.py (WebSocket integration)
frontend/src/app/documents/page.tsx (real-time updates)
```

**Implementation:**
Already partially implemented via WebSocket in `page.tsx`:
- Lines 36-83: WebSocket listeners exist
- Need to emit events from Celery tasks

```python
# In backend/tasks.py - after each file completes

from backend.websocket_manager import manager

await manager.send_personal_message(
    message={
        'type': 'document_created',
        'data': {
            'doc_id': doc_id,
            'filename': filename,
            'cluster_id': cluster_id
        }
    },
    user_id=user_id
)
```

**Expected Result:**
- User sees files appearing in real-time
- Better UX (feels 50% faster)
- Can start working with completed files immediately

---

## 🎯 Recommended Implementation Order

### Phase 1: Quick Wins (Week 1)
1. ✅ **Smart File Filtering** (30 min) - Immediate 30% improvement
2. ✅ **Verify Redis Caching** (15 min) - Ensure it's working
3. ✅ **Add progress logging** (15 min) - Better debugging

**Expected result:** 29 files in ~15 minutes (35% improvement)

### Phase 2: Major Optimization (Week 2)
4. ✅ **Batch Embeddings** (2 hours) - 40% improvement
5. ✅ **Parallel Queue Routing** (1 hour) - 20% improvement

**Expected result:** 29 files in ~7 minutes (70% improvement)

### Phase 3: UX Enhancement (Week 3)
6. ✅ **Real-time WebSocket Updates** (4 hours) - Perceived 50% improvement

**Expected result:** User satisfaction high, feels instant

---

## 📊 Performance Targets

### Current State:
| Metric | Value |
|--------|-------|
| 29 files processing time | 23 minutes |
| Per-file average | 47 seconds |
| User experience | Poor (long wait, no feedback) |
| API calls per file | 2 (concepts + embeddings) |
| Total API calls | 58 for 29 files |

### After Phase 1:
| Metric | Value |
|--------|-------|
| 29 files processing time | **15 minutes** (35% faster) |
| Per-file average | 31 seconds |
| User experience | Same (no feedback) |
| API calls per file | 1-2 (skip for small files) |
| Total API calls | ~40 for 29 files |

### After Phase 2:
| Metric | Value |
|--------|-------|
| 29 files processing time | **7 minutes** (70% faster) |
| Per-file average | 14 seconds |
| User experience | Same (no feedback) |
| API calls per file | 1-2 (batched) |
| Total API calls | 5-10 batch calls total |

### After Phase 3:
| Metric | Value |
|--------|-------|
| 29 files processing time | **7 minutes** (same speed) |
| Per-file average | 14 seconds |
| User experience | **Excellent** (real-time updates) |
| Perceived speed | Feels < 2 minutes |

---

## 🔧 Configuration Changes Needed

### Environment Variables (.env)
```bash
# Batch processing
BATCH_EMBEDDING_SIZE=20  # Process 20 files at once
BATCH_EMBEDDING_TIMEOUT=10  # Wait max 10s to accumulate batch

# Smart filtering
SKIP_SMALL_FILES=true
MIN_FILE_SIZE_FOR_CONCEPTS=500  # Skip files < 500 chars

# Queue configuration
CELERY_FAST_QUEUE_WORKERS=4
CELERY_SLOW_QUEUE_WORKERS=2
CELERY_AI_QUEUE_WORKERS=4
```

### Docker Compose Changes
```yaml
# Add specialized workers
celery-worker-fast:
  <<: *celery-base
  command: celery -A backend.celery_app worker -Q fast -c 4 -n fast@%h

celery-worker-slow:
  <<: *celery-base
  command: celery -A backend.celery_app worker -Q slow -c 2 -n slow@%h
```

---

## 🧪 Testing Strategy

### Performance Tests:
1. **Baseline:** Process 29-file ZIP (current: 23 min)
2. **After Phase 1:** Same ZIP (target: 15 min)
3. **After Phase 2:** Same ZIP (target: 7 min)
4. **Stress test:** 100-file ZIP, 500-file ZIP

### Files to Test With:
- Small files (< 1KB): readme.md, .txt
- Medium files (1KB-50KB): .json, .py
- Large files (50KB-500KB): datasets, PDFs
- Mixed ZIPs (small + large)
- Nested ZIPs (ZIP in ZIP)

---

## 💰 Cost Optimization

### Current Cost (per 29-file ZIP):
- Concept extraction: 29 calls × $0.0001 = **$0.0029**
- Embeddings: 29 calls × $0.00002 = **$0.00058**
- **Total: ~$0.0035 per ZIP**

### After Optimizations:
- Concept extraction: 22 calls × $0.0001 = **$0.0022** (skip 7 small files)
- Embeddings: 3 batch calls × $0.00002 = **$0.00006** (batch processing)
- **Total: ~$0.0023 per ZIP (34% cost reduction)**

### Annual Savings (estimate):
- If processing 1,000 ZIPs/month
- Current: $42/year
- Optimized: $28/year
- **Savings: $14/year** (small scale, but scales with usage)

---

## 📝 Implementation Checklist

### Phase 1: Smart File Filtering
- [ ] Add skip logic to `backend/tasks.py`
- [ ] Define `SKIP_CONCEPT_FILES` constant
- [ ] Add file size check (< 500 chars)
- [ ] Add logging for skipped files
- [ ] Test with 29-file ZIP
- [ ] Verify concepts still extracted for important files

### Phase 2: Batch Embeddings
- [ ] Modify `backend/embedding_service.py` for batching
- [ ] Update `backend/tasks.py` to collect files before embedding
- [ ] Add batch size configuration (default: 20)
- [ ] Handle batch errors gracefully
- [ ] Test with various batch sizes
- [ ] Monitor API rate limits

### Phase 3: Parallel Queues
- [ ] Define queue routes in `backend/celery_app.py`
- [ ] Add queue selection logic in `backend/tasks.py`
- [ ] Update `docker-compose.yml` with queue workers
- [ ] Test queue distribution
- [ ] Monitor worker utilization

### Phase 4: Real-time Updates
- [ ] Add WebSocket emitters to `backend/tasks.py`
- [ ] Test WebSocket connection stability
- [ ] Update frontend to display real-time progress
- [ ] Add progress bar UI component
- [ ] Handle WebSocket disconnections

---

## 🚨 Risks & Mitigation

### Risk 1: OpenAI Rate Limits
**Problem:** Batching may hit rate limits faster
**Mitigation:**
- Implement exponential backoff
- Add rate limit monitoring
- Queue requests during high load

### Risk 2: Memory Usage
**Problem:** Batching 20 files loads all in memory
**Mitigation:**
- Limit batch size to 20 files max
- Stream large files instead of loading fully
- Monitor container memory usage

### Risk 3: Failed Batches
**Problem:** If 1 file in batch fails, entire batch fails
**Mitigation:**
- Catch exceptions per file in batch
- Retry failed files individually
- Log failures clearly

---

## 📈 Success Metrics

### Performance:
- ✅ 29-file ZIP: < 8 minutes (current: 23 minutes)
- ✅ Per-file average: < 15 seconds (current: 47 seconds)
- ✅ 100-file ZIP: < 20 minutes

### User Experience:
- ✅ Real-time progress visible
- ✅ First file appears < 30 seconds
- ✅ Can work with partial results

### Cost:
- ✅ 30% reduction in API calls
- ✅ Lower OpenAI costs

### Reliability:
- ✅ No failed uploads due to optimization
- ✅ All files processed successfully
- ✅ Error handling improved

---

**Last Updated:** 2025-11-28
**Document Owner:** SyncBoard Development Team
**Review Date:** Check progress in 2 weeks
