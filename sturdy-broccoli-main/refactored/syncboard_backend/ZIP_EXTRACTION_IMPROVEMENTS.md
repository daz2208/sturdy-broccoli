# ZIP Extraction Multi-Document Support

**Date:** 2025-11-22
**Status:** Design Document - Not Yet Implemented
**Priority:** Medium

---

## 🏆 HIGHEST IMPACT IMPROVEMENTS FOR PROJECT

### #1: Replace In-Memory TF-IDF with External Vector Database
**Priority:** 🔥 CRITICAL - 10x User Experience Improvement
**Effort:** 4-6 hours
**ROI:** Massive

#### Current Bottleneck
**File:** `backend/vector_store.py`

**Problems:**
- ❌ **In-memory only** - Lost on restart, slow rebuilds
- ❌ **TF-IDF = keyword matching** - NOT semantic understanding
- ❌ **Limited scale** - ~10k-50k docs max before performance degrades
- ❌ **No persistence** - Rebuilds from DB on every startup

**Example:**
```
Search: "Python tutorial"
Current (TF-IDF): Finds exact keyword matches only
Semantic Search: Finds "Learn Python coding", "Python beginner guide", etc.
```

#### The Win with Vector Database
**Options:** Pinecone, Weaviate, Qdrant, ChromaDB

**Gains:**
1. **10-100x Better Search** 🎯
   - Understands meaning, not just keywords
   - "machine learning intro" finds "ML basics for beginners"
   - Cross-lingual search potential

2. **Scale to Millions** 📈
   - Current: 10k-50k docs
   - With Vector DB: Millions of documents
   - No performance degradation

3. **Persistent Storage** 💾
   - No rebuild on restart
   - Instant startup times
   - Distributed deployment ready

4. **Smarter AI Features** 🤖
   - **Build suggestions** → Actually understand project context
   - **Auto-clustering** → Group by semantic similarity
   - **Related documents** → Find truly related content

#### Implementation Plan
```python
# 1. Replace backend/vector_store.py with:
from pinecone import Pinecone
import openai

class VectorStore:
    def __init__(self):
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index("syncboard")

    async def add_document(self, doc_id: int, content: str):
        # Generate embedding using OpenAI (already have API key!)
        embedding = openai.Embedding.create(
            input=content,
            model="text-embedding-3-small"  # Cheap: $0.02/1M tokens
        )["data"][0]["embedding"]

        # Store in Pinecone
        self.index.upsert([(str(doc_id), embedding, {"content": content})])

    async def search(self, query: str, top_k: int = 10):
        # Semantic search
        query_embedding = openai.Embedding.create(
            input=query,
            model="text-embedding-3-small"
        )["data"][0]["embedding"]

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        return results
```

**Changes Required:**
1. Add Pinecone/Weaviate client (2 hours)
2. Replace TF-IDF calls with vector search (2 hours)
3. Add embedding generation pipeline (1 hour)
4. Update tests (1 hour)

**Cost:** ~$5-20/month for Pinecone (scales with usage)

---

### #2: Actually USE Redis Caching
**Priority:** 🔥 HIGH - 2-5x Speed Improvement for FREE
**Effort:** 2-3 hours
**ROI:** Immediate

#### Current State
**Files:** `backend/redis_client.py`, `backend/cache.py`

**Status:**
- ✅ Redis is installed and running in Docker
- ✅ Redis client is configured
- ❌ **Almost nothing uses it!**

#### The Free Win
Redis is already there, just need to use it:

**Cache These (Huge Wins):**
1. **Concept extraction results** (expensive LLM calls)
   ```python
   @cache_result(ttl=3600)  # 1 hour
   async def extract_concepts(content: str):
       # Avoid re-extracting same content
   ```

2. **Build suggestions** (expensive LLM calls)
   ```python
   @cache_result(ttl=1800)  # 30 min
   async def generate_suggestions(knowledge_summary: str):
       # Cache by knowledge state hash
   ```

3. **Search results** (expensive vector operations)
   ```python
   @cache_result(ttl=300)  # 5 min
   async def search(query: str, filters: dict):
       # Cache frequent searches
   ```

4. **Analytics calculations** (expensive aggregations)
   ```python
   @cache_result(ttl=600)  # 10 min
   async def get_analytics(time_period: str):
       # Cache dashboard data
   ```

#### Implementation
```python
# backend/cache.py - ADD THIS
import functools
import json
import hashlib
from .redis_client import redis_client

def cache_result(ttl: int = 300):
    """Decorator to cache function results in Redis."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{_hash_args(args, kwargs)}"

            # Try cache first
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Cache miss - compute
            result = await func(*args, **kwargs)

            # Store in cache
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )

            return result
        return wrapper
    return decorator

def _hash_args(args, kwargs) -> str:
    """Create hash of function arguments."""
    data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(data.encode()).hexdigest()
```

**Usage:**
```python
# backend/concept_extractor.py
from backend.cache import cache_result

@cache_result(ttl=3600)  # Cache for 1 hour
async def extract(self, content: str, source_type: str):
    # Expensive LLM call here
    return extraction_result
```

**Impact:**
- **Concept extraction:** 100x faster (cached)
- **Build suggestions:** 100x faster (cached)
- **Search:** 5-10x faster
- **Analytics:** 5x faster
- **API response times:** 50-80% reduction

**Cost:** $0 (already have Redis running!)

---

### #3: Hybrid Search (Combine Keyword + Semantic)
**Priority:** MEDIUM - Best of Both Worlds
**Effort:** 2 hours (after Vector DB implemented)

**Why:** Sometimes users want exact keywords (like error codes), sometimes semantic.

**Implementation:**
```python
async def hybrid_search(query: str, alpha: float = 0.5):
    """
    Combine TF-IDF keyword search with semantic vector search.

    alpha=0.0 → Pure keyword
    alpha=1.0 → Pure semantic
    alpha=0.5 → Balanced (recommended)
    """
    # Get both result sets
    keyword_results = await tfidf_search(query, top_k=20)
    semantic_results = await vector_search(query, top_k=20)

    # Reciprocal Rank Fusion (RRF)
    scores = {}
    for rank, (doc_id, score) in enumerate(keyword_results):
        scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) / (rank + 60)

    for rank, (doc_id, score) in enumerate(semantic_results):
        scores[doc_id] = scores.get(doc_id, 0) + alpha / (rank + 60)

    # Sort by combined score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
```

---

### Implementation Priority Order

**Phase 1 (Weekend - 6-9 hours):**
1. ✅ Add Redis caching decorators (2 hours) → **Immediate 2-5x speed win**
2. ✅ Cache concept extraction (1 hour) → **Save $$ on OpenAI**
3. ✅ Cache search results (1 hour) → **Faster UX**
4. ✅ Setup Vector DB (Pinecone/Weaviate) (2-3 hours) → **Foundation**

**Phase 2 (Next Sprint - 4-6 hours):**
1. ✅ Migrate to vector search (3 hours) → **10x better search**
2. ✅ Add hybrid search (2 hours) → **Best of both worlds**
3. ✅ Update tests (1 hour)

**Phase 3 (Future):**
1. Multi-document ZIP extraction (from this doc)
2. Advanced clustering with embeddings
3. Cross-document relationship detection

---

### Cost-Benefit Analysis

| Improvement | Effort | Cost/Month | Speed Gain | UX Gain | Priority |
|-------------|--------|------------|------------|---------|----------|
| Redis Caching | 3h | $0 | 2-5x | ⭐⭐⭐ | 🔥 DO NOW |
| Vector DB | 6h | $5-20 | 10-100x search | ⭐⭐⭐⭐⭐ | 🔥 DO NOW |
| Hybrid Search | 2h | $0 | 20% better | ⭐⭐⭐⭐ | Later |
| Multi-doc ZIP | 8h | $0 | 0 | ⭐⭐⭐ | Later |

**ROI Winner:** Redis caching (FREE speed boost)
**UX Winner:** Vector DB (transformative search experience)

---

## Current Behavior (ZIP Extraction)

### What Works ✅
- ZIP files are recursively extracted (up to 5 levels deep)
- All supported file types are processed (code, JSON, docs, PDFs, etc.)
- Safety features: max 1000 files, 10MB per file, zip bomb protection
- Output is ONE concatenated document with all files

### Current Output Format
```
ZIP ARCHIVE: my_project.zip
=== file1.py ===
[content]
=== file2.json ===
[content]
=== nested.zip ===
[recursively extracted content]
```

**Result:** ALL files → ONE document in database

---

## The Problem

### Use Case 1: n8n Automations
User uploads `automations.zip`:
```
automations.zip
├── customer_onboarding.json
├── slack_notifier.json
└── data_sync.json
```

**Current:** All 3 JSON files merged into ONE document
**Desired:** Each JSON file = separate document for individual management

### Use Case 2: Code Projects
User uploads `builds.zip`:
```
builds.zip
├── build1/
│   ├── main.py
│   └── utils.py
├── build2/
│   ├── main.py
│   └── utils.py
└── build3/
    ├── main.py
    └── utils.py
```

**Current:** All files → one document
**Problem:** Files lose folder context, can't tell which build they belong to

---

## Proposed Solutions

### Option 1: File-Based Separation
**Best for:** n8n automations, individual JSON/config files

Each file in ZIP → Separate document
- `customer_onboarding.json` → Document 1
- `slack_notifier.json` → Document 2
- `data_sync.json` → Document 3

**Pros:**
- Easy to manage individual files
- Good for collections of independent files

**Cons:**
- Loses folder context
- Code projects would be fragmented

---

### Option 2: Keep Folder Structure Visible
**Enhancement to current approach**

Add clear folder headers to existing single-document output:

```
=== BUILD 1 (Folder: build1/) ===
--- main.py ---
[content]
--- utils.py ---
[content]

=== BUILD 2 (Folder: build2/) ===
--- main.py ---
[content]
--- utils.py ---
[content]
```

**Pros:**
- Minimal code changes
- Preserves context visually
- No breaking changes

**Cons:**
- Still one giant document
- Can't manage individual parts

---

### Option 3: Folder-Based Separation
**Best for:** Code projects with organized structure

Each top-level folder → Separate document
- `build1/` (all files) → Document 1
- `build2/` (all files) → Document 2
- `build3/` (all files) → Document 3

**Pros:**
- Maintains logical grouping
- Good for structured projects

**Cons:**
- Not ideal for flat ZIP structures
- Requires folder naming conventions

---

### Option 4: Smart Detection (RECOMMENDED)
**Auto-detect best approach based on ZIP content**

#### Detection Logic:
```python
if mostly_json_files and flat_structure:
    # Use file-based separation (Option 1)
    # Good for: n8n automations, config collections

elif has_folder_structure and multiple_files_per_folder:
    # Use folder-based separation (Option 3)
    # Good for: code projects, organized builds

else:
    # Use current single-document approach
    # Good for: simple archives, mixed content
```

#### Smart Rules:
- **>70% JSON files + flat structure** → File-based
- **Clear folder structure + code files** → Folder-based
- **Mixed/complex** → Single document with folder headers

**Pros:**
- Best of both worlds
- User doesn't need to choose
- Handles different use cases automatically

**Cons:**
- More complex implementation
- Needs good heuristics

---

## Implementation Requirements

### Current System Architecture
```
Upload → ingest.py → extract_zip_archive() → ONE string → ONE document → database
```

### Required Changes for Multi-Document Support

#### 1. Change Return Type
**File:** `backend/ingest.py`

```python
# CURRENT
def extract_zip_archive(...) -> str:
    return single_concatenated_string

# NEW
def extract_zip_archive(...) -> Union[str, List[Dict]]:
    # Single document mode
    if should_use_single_document:
        return single_concatenated_string

    # Multi-document mode
    return [
        {
            "filename": "customer_onboarding.json",
            "content": "...",
            "folder": None,
            "metadata": {...}
        },
        {
            "filename": "main.py",
            "content": "...",
            "folder": "build1",
            "metadata": {...}
        }
    ]
```

#### 2. Update Upload Router
**File:** `backend/routers/uploads.py`

```python
# Handle both single and multiple documents
extracted = await ingest_upload_file(filename, content_bytes)

if isinstance(extracted, list):
    # Multiple documents - create one for each
    doc_ids = []
    for item in extracted:
        doc_id = await create_document(item["content"], item["metadata"])
        doc_ids.append(doc_id)

    return {"doc_ids": doc_ids, "count": len(doc_ids)}
else:
    # Single document - existing logic
    doc_id = await create_document(extracted, metadata)
    return {"doc_id": doc_id}
```

#### 3. Update Frontend Response Handler
**File:** `backend/static/app.js`

```javascript
// Handle both single and multiple document responses
if (response.doc_ids) {
    // Multiple documents created
    showSuccess(`✅ Created ${response.count} documents from ZIP`);
    displayMultipleDocuments(response.doc_ids);
} else {
    // Single document - existing logic
    showSuccess(`✅ Document ${response.doc_id} created`);
    displayDocument(response.doc_id);
}
```

#### 4. Add Smart Detection Function
**File:** `backend/ingest.py`

```python
def detect_zip_extraction_strategy(zip_file) -> str:
    """
    Analyze ZIP contents and determine best extraction strategy.

    Returns:
        'file-based' | 'folder-based' | 'single-document'
    """
    files = [f for f in zip_file.infolist() if not f.is_dir()]

    # Count file types
    json_count = sum(1 for f in files if f.filename.endswith('.json'))
    total_count = len(files)

    # Check structure
    has_folders = any('/' in f.filename for f in files)
    folders = set(f.filename.split('/')[0] for f in files if '/' in f.filename)

    # Decision logic
    if json_count / total_count > 0.7 and not has_folders:
        return 'file-based'

    elif has_folders and len(folders) > 1:
        return 'folder-based'

    else:
        return 'single-document'
```

---

## Testing Requirements

### Test Cases

#### 1. n8n Automations (File-Based)
```
Input: automations.zip (5 JSON files, flat structure)
Expected: 5 separate documents created
Verify: Each document has correct filename and content
```

#### 2. Code Project (Folder-Based)
```
Input: builds.zip (3 folders with code files)
Expected: 3 documents (one per folder)
Verify: Each document contains all files from its folder
```

#### 3. Mixed Content (Single Document)
```
Input: mixed.zip (various files, no clear pattern)
Expected: 1 document with all content
Verify: Current behavior maintained
```

#### 4. Nested ZIPs
```
Input: nested.zip with multiple levels
Expected: Strategy applied at each level
Verify: No infinite recursion, respects limits
```

#### 5. Edge Cases
- Empty folders
- Files with same names in different folders
- Very large ZIPs (near limits)
- Malformed ZIPs

---

## Migration Considerations

### Backward Compatibility
- **Option 2 (folder headers):** ✅ No breaking changes
- **Options 1, 3, 4 (multi-document):** ⚠️ Changes API response format

### Rollout Strategy
1. **Phase 1:** Add folder headers (Option 2) - safe, immediate value
2. **Phase 2:** Implement multi-document infrastructure
3. **Phase 3:** Add smart detection (Option 4)
4. **Phase 4:** Deprecate single-document-only mode (optional)

### API Versioning
Consider adding version parameter:
```
POST /upload_file?zip_mode=auto|single|file-based|folder-based
```

---

## Performance Considerations

### Current Performance
- Single document → One DB write
- Memory: Load entire ZIP output string

### Multi-Document Performance
- N documents → N DB writes (bulk operation needed)
- Memory: Process files incrementally
- Consider: Transaction handling for atomicity

### Optimization Ideas
- Bulk insert for multiple documents
- Lazy loading for large ZIPs
- Progress callbacks for UI feedback

---

## Security Considerations

### Existing Protections (Keep)
- Max recursion depth: 5 levels
- Max file count: 1000 files
- Max file size: 10MB per file
- Skip hidden/system files

### New Considerations
- Document count limits (prevent abuse)
- Filename sanitization (prevent path traversal)
- Metadata validation (structured data)

---

## Configuration

### Suggested Environment Variables
```bash
# ZIP extraction mode
SYNCBOARD_ZIP_MODE=auto|single|file-based|folder-based  # default: auto

# Multi-document limits
SYNCBOARD_ZIP_MAX_DOCUMENTS=100  # max documents per ZIP

# Smart detection thresholds
SYNCBOARD_ZIP_JSON_THRESHOLD=0.7  # 70% JSON for file-based mode
SYNCBOARD_ZIP_MIN_FOLDERS=2  # minimum folders for folder-based mode
```

---

## Implementation Steps

### Quick Fix (1-2 hours)
**Option 2: Add folder headers**
1. Modify `extract_zip_archive()` to add folder headers
2. Test with existing upload flow
3. Deploy (no breaking changes)

### Full Solution (8-12 hours)
**Option 4: Smart detection with multi-document support**
1. Add smart detection function (1 hour)
2. Modify `extract_zip_archive()` return type (2 hours)
3. Update upload router logic (2 hours)
4. Update frontend handling (2 hours)
5. Add bulk document creation (1 hour)
6. Write comprehensive tests (3 hours)
7. Update API documentation (1 hour)

---

## Related Files

### Files to Modify
- `backend/ingest.py` - Core extraction logic
- `backend/routers/uploads.py` - Upload handling
- `backend/services.py` - Document creation
- `backend/static/app.js` - Frontend response handling

### Files to Review
- `tests/test_ingestion_phase3.py` - ZIP extraction tests
- `tests/test_api_endpoints.py` - Upload endpoint tests

### Documentation to Update
- `README.md` - Feature description
- API documentation (OpenAPI spec)

---

## Decision Required

**Choose ONE approach:**
- [ ] **Option 2** - Quick fix with folder headers (safe, fast)
- [ ] **Option 4** - Smart detection with multi-document (comprehensive, more work)
- [ ] **Both** - Phase 1: Option 2, Phase 2: Option 4

**Recommended:** Start with Option 2 for immediate value, then implement Option 4 in next sprint.

---

## Notes
- Current ZIP extraction is production-ready for single-document use case
- No bugs found, this is a feature enhancement request
- User feedback: n8n automations need individual document management
- Context preservation is critical for code projects
