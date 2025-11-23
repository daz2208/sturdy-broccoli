# Smart ZIP Extraction Implementation - Session Summary

**Date:** 2025-11-23
**Status:** ✅ Backend Complete, ⚠️ Frontend Issue Found

---

## 🎯 Problem Statement

User uploaded `n8n-templates-main.zip` (20 JSON workflow files) and all 20 files were **concatenated into 1 massive document**. This made AI queries ineffective because:
- AI couldn't distinguish between individual workflows
- Search returned "one big blob" instead of specific workflows
- User wanted: 20 separate documents (one per workflow file)

---

## ✅ Implementation Complete

### 1. **backend/ingest.py** - Smart ZIP Detection
**Lines Modified:** Added 3 new functions + modified `extract_zip_archive()`

**New Function: `detect_zip_extraction_strategy()` (lines 1253-1317)**
```python
def detect_zip_extraction_strategy(zip_file) -> str:
    """
    Analyze ZIP contents and determine extraction strategy.

    Returns: 'file-based' | 'folder-based' | 'single-document'

    Rules:
    - >70% JSON files → file-based (perfect for n8n workflows)
    - Multiple folders + code files → folder-based (code projects)
    - Otherwise → single-document (legacy behavior)
    """
```

**New Function: `_extract_zip_file_based()` (lines 1320-1392)**
- Each file in ZIP becomes a separate document
- Returns `List[Dict]` with document metadata
- Each dict contains: filename, content, folder, source_file, original_zip, metadata

**New Function: `_extract_zip_folder_based()` (lines 1395-1486)**
- Each top-level folder becomes a separate document
- Good for monorepos with multiple projects

**Modified: `extract_zip_archive()` signature (line 1489)**
```python
def extract_zip_archive(
    content_bytes: bytes,
    filename: str,
    current_depth: int = 0,
    max_depth: int = 5,
    file_counter: Optional[dict] = None,
    multi_document: bool = True  # NEW PARAMETER
) -> Union[str, List[Dict]]:  # NEW RETURN TYPE (was just str)
```

**Detection Logic (lines 1509-1527)**:
```python
if current_depth == 0 and multi_document:
    strategy = detect_zip_extraction_strategy(zip_file)

    if strategy == 'file-based':
        return _extract_zip_file_based(zip_file, filename, file_counter)
    elif strategy == 'folder-based':
        return _extract_zip_folder_based(zip_file, filename, file_counter)
    # Otherwise fall through to single-document
```

---

### 2. **backend/tasks.py** - Multi-Document Processing
**Lines Modified:** Added new function + modified `process_file_upload()`

**New Function: `process_multi_document_zip()` (lines 196-387)**
- Processes each document from List[Dict] through full pipeline
- Each document gets:
  - AI concept extraction
  - Clustering (finds best cluster or creates new)
  - Vector store addition
  - Database persistence
  - Chunking for RAG
  - Hierarchical summarization
- Progress updates: "Processing file 1/20: github-workflow-builder.json..."
- Returns: `{"status": "multi_document_success", "total_documents": 20, "doc_ids": [...], "filenames": [...]}`

**Modified: `process_file_upload()` (lines 260-276)**
```python
document_text_or_list = ingest.ingest_upload_file(filename_safe, file_bytes, clean_for_ai=True)

# Check if ZIP returned multiple documents
if isinstance(document_text_or_list, list):
    # MULTI-DOCUMENT ZIP EXTRACTION
    return process_multi_document_zip(
        self=self,
        user_id=user_id,
        filename=filename_safe,
        documents_list=document_text_or_list,
        kb_id=kb_id
    )

# SINGLE DOCUMENT: Continue with existing flow
document_text = document_text_or_list
```

---

### 3. **backend/routers/jobs.py** - No Changes Needed ✅
The jobs router already copies all result fields to the response, so it automatically handles both:
- Single document: `{doc_id, cluster_id, concepts}`
- Multi-document: `{status: "multi_document_success", total_documents, doc_ids, filenames}`

---

### 4. **backend/static/app.js** - Frontend Updates
**Lines Modified:** 3193-3232 (pollJobStatus function)

**Updated SUCCESS handler (lines 3198-3228)**:
```javascript
if (data.status === 'multi_document_success') {
    // Multi-document ZIP upload
    const totalDocs = data.total_documents || 0;
    const zipName = data.original_filename || 'archive.zip';

    showToast(
        `✅ ZIP extracted! ${totalDocs} documents created from ${zipName}`,
        'success'
    );

    // Show detailed breakdown in console
    if (data.filenames && data.filenames.length > 0) {
        const fileList = data.filenames.slice(0, 5).join(', ');
        const remaining = data.filenames.length > 5 ? ` (+${data.filenames.length - 5} more)` : '';
        console.log(`📦 Extracted files: ${fileList}${remaining}`);
    }
}
// Single document upload (existing behavior)
else if (data.document_id || data.doc_id) {
    const docId = data.document_id || data.doc_id;
    showToast(`✅ Uploaded! Doc ${docId} → Cluster ${clusterId}`, 'success');
}
```

---

## 🔄 Deployment Status

### ✅ Completed:
1. Code changes implemented in all 3 files
2. Celery workers restarted with new code at 22:13 (11 hours ago)
3. Both workers (celery + celery-worker-2) loaded new code successfully
4. Workers are running and idle, ready for tasks

### ✅ Verified Working:
- **2 YouTube URLs uploaded successfully**
  - URL 1: `https://www.youtube.com/watch?v=QM1D8Sx4N3U` → doc_id 3 (7 chunks)
  - URL 2: `https://www.youtube.com/watch?v=Q46OLxFshAQ` → doc_id 3 (11 chunks)
- Both completed with full AI processing, chunking, summarization
- Redis shows both tasks: `{"status": "SUCCESS", ...}`

---

## ⚠️ Known Issues

### Frontend Polling Stuck
**Symptom:** UI shows "loading" indefinitely even though tasks completed successfully

**Evidence:**
- Redis shows tasks with `"status": "SUCCESS"`
- Celery logs show `Task succeeded in X seconds`
- Frontend keeps polling forever
- User had to refresh page to stop it

**Possible Causes:**
1. Frontend polling timeout too long (5 minutes)
2. Job status endpoint not returning correct format
3. Race condition between task completion and frontend check
4. Browser cache serving old JavaScript

**Temporary Workaround:**
- Refresh the page after ~3 minutes
- Check documents list to verify upload completed

**To Debug:**
1. Check browser DevTools → Network → Filter `/jobs/{job_id}/status` responses
2. Verify response contains `"status": "SUCCESS"` field
3. Check if `pollJobStatus()` function receives and handles SUCCESS state

---

## 🧪 Testing Plan (Not Yet Tested)

### Test Case 1: n8n ZIP (20 JSON files)
1. Upload: `C:\Users\fuggl\Desktop\n8n-templates-main\n8n-templates-main\n8n-templates-main.zip`
2. **Expected Detection**: File-based (20/20 = 100% JSON files > 70% threshold)
3. **Expected Result**: 20 separate documents
4. **Expected Message**: `✅ ZIP extracted! 20 documents created from n8n-templates-main.zip`
5. **Expected Files**:
   - `github-workflow-builder.json` → doc_id X
   - `slack-notification-system.json` → doc_id Y
   - `ai-overview-analyzer.json` → doc_id Z
   - ...17 more

### Test Case 2: Code Project ZIP (multiple folders)
1. Upload a monorepo with `/frontend`, `/backend`, `/shared`
2. **Expected Detection**: Folder-based (multiple folders with code files)
3. **Expected Result**: 3 documents (one per folder)

### Test Case 3: Mixed ZIP (< 70% JSON)
1. Upload ZIP with 5 JSON + 10 Python files
2. **Expected Detection**: Single-document (33% JSON < 70%)
3. **Expected Result**: 1 concatenated document (legacy behavior)

---

## 📊 Expected Behavior: Before vs After

### Before (Old Concatenated Method):
```
n8n-templates-main.zip uploaded
↓
1 document created (doc_id 3)
↓
Content: All 20 JSON files concatenated
File size: 203 chunks
↓
AI query: "What n8n workflows do I have?"
Response: "I found something about n8n in a large document..."
```

### After (Smart Extraction):
```
n8n-templates-main.zip uploaded
↓
20 documents created (doc_ids 5-24)
↓
Each document:
  - Filename: github-workflow-builder.json
  - Concepts: [GitHub, workflow automation, CI/CD]
  - Cluster: Automation
  - Chunks: ~10 chunks per document
↓
AI query: "What n8n workflows do I have?"
Response: "You have 20 n8n workflows:
  1. GitHub Workflow Builder (doc 5)
  2. Slack Notification System (doc 6)
  3. AI Overview Analyzer (doc 7)
  ..."
```

---

## 🔍 How It Works (Technical Flow)

### Step 1: Upload ZIP File
```
User uploads n8n-templates-main.zip
↓
FastAPI uploads router: /upload_file
↓
Queues Celery task: process_file_upload.delay()
↓
Returns job_id to frontend
```

### Step 2: Backend Detection
```
Celery worker picks up task
↓
tasks.py: process_file_upload()
↓
Line 262: document_text_or_list = ingest.ingest_upload_file()
↓
ingest.py: extract_zip_archive()
↓
Line 1509: detect_zip_extraction_strategy()
↓
Counts files: 20 JSON / 20 total = 100%
↓
Decision: 100% > 70% → file-based extraction
```

### Step 3: File-Based Extraction
```
ingest.py: _extract_zip_file_based()
↓
Loops through each file in ZIP:
  For each file:
    - Extract content
    - Process with ingest_upload_file()
    - Create document dict: {filename, content, metadata}
    - Append to list
↓
Returns: List[Dict] with 20 documents
```

### Step 4: Multi-Document Processing
```
tasks.py: process_file_upload()
↓
Line 265: isinstance(document_text_or_list, list) → True
↓
Line 267: process_multi_document_zip()
↓
For each document (20 iterations):
  - AI concept extraction (OpenAI API)
  - Add to vector store
  - Create metadata
  - Find/create cluster
  - Save to database
  - Chunk for RAG (10-15 chunks per doc)
  - Generate hierarchical summaries
  - Progress update: "Processing file 1/20..."
↓
Returns: {
  "status": "multi_document_success",
  "total_documents": 20,
  "doc_ids": [5,6,7,...,24],
  "filenames": ["github-workflow-builder.json", ...]
}
```

### Step 5: Frontend Display
```
Frontend polls: /jobs/{job_id}/status every 1 second
↓
When status === 'SUCCESS':
  - Check if data.status === 'multi_document_success'
  - Show toast: "✅ ZIP extracted! 20 documents created"
  - Refresh clusters list
```

---

## 🐛 Debugging Commands

### Check Celery Workers Status:
```bash
cd C:\Users\fuggl\Desktop\sturdy-broccoli-main\sturdy-broccoli-main\refactored\syncboard_backend
docker-compose ps
```

### View Celery Logs (Live):
```bash
docker-compose logs -f celery celery-worker-2
```

### Check Redis for Job Status:
```bash
docker-compose exec redis redis-cli keys "celery-task-meta-*"
docker-compose exec redis redis-cli get "celery-task-meta-{job_id}"
```

### Restart Celery Workers (After Code Changes):
```bash
docker-compose restart celery celery-worker-2
```

### Check Database Documents:
```bash
docker-compose exec backend python debug_kb.py
```

---

## 📝 Next Steps

1. **Fix Frontend Polling Issue** (PRIORITY)
   - Debug `pollJobStatus()` in app.js
   - Check browser console for errors
   - Verify job status endpoint response format

2. **Test Smart ZIP Extraction**
   - Upload n8n ZIP again (new code will process it)
   - Verify 20 separate documents created
   - Test AI queries: "What n8n workflows do I have?"

3. **Clean Up Old Data**
   - Delete old concatenated ZIP document (doc_id 3 from old upload)
   - Re-upload ZIP with smart extraction

4. **Verify AI Queries Work Better**
   - Compare: Old (1 blob) vs New (20 docs)
   - Test specific queries: "Show me the GitHub workflow"

---

## 🔧 Files Modified

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `backend/ingest.py` | +300 lines | Smart ZIP detection & extraction |
| `backend/tasks.py` | +200 lines | Multi-document processing pipeline |
| `backend/static/app.js` | ~40 lines | Frontend multi-document display |

**Total:** ~540 lines of new code

---

## 💾 Backup & Rollback

### To Rollback (If Needed):
```bash
# Revert changes
git checkout backend/ingest.py
git checkout backend/tasks.py
git checkout backend/static/app.js

# Restart workers
docker-compose restart celery celery-worker-2
```

### Original Behavior:
- All ZIP files: single concatenated document
- Return type: `str`
- No detection logic

---

## 📞 Support Info

**Issue:** Frontend stuck on loading after successful upload
**Evidence:** Redis shows SUCCESS, Celery logs show completion, frontend keeps polling
**Workaround:** Refresh page after 3 minutes, check documents list
**Next Debug:** Check browser DevTools Network tab for `/jobs/{job_id}/status` responses

**Session Context Running Low:** 122K / 200K tokens used
