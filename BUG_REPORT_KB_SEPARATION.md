# Bug Report: Knowledge Base Separation Not Working in Build Suggestions
## Critical Data Isolation Issue

**Discovery Date:** November 19, 2025
**Severity:** 🔴 **HIGH** - Data isolation issue
**Status:** 🐛 **Confirmed Bug**
**Affected Endpoint:** `/what_can_i_build`

---

## Summary

The build suggestions endpoint (`/what_can_i_build`) is **NOT properly using knowledge base separation**. It mixes data from all knowledge bases together before filtering by username, which can cause:
- Data leakage between users in different KBs
- Document ID collisions if multiple KBs use the same IDs
- Incorrect cluster attribution
- Incorrect search results

---

## Investigation Results

### ✅ 1. Database Structure - CORRECT
**Query:**
```sql
SELECT id, name, knowledge_base_id FROM clusters ORDER BY knowledge_base_id, id;
```

**Results:**
```
id |               name               |          knowledge_base_id
----+----------------------------------+--------------------------------------
  0 | ai automation freelancing        | fdb42d38-892d-48e8-bc4e-1f92452dbc7d
  1 | rag agent tutorials              | fdb42d38-892d-48e8-bc4e-1f92452dbc7d
  2 | self-hosting workflow automation | fdb42d38-892d-48e8-bc4e-1f92452dbc7d
  3 | ai automation and monetization   | fdb42d38-892d-48e8-bc4e-1f92452dbc7d
  4 | ai monetization strategies       | fdb42d38-892d-48e8-bc4e-1f92452dbc7d
```

**Status:** ✅ **Database correctly stores KB IDs**
- All clusters have `knowledge_base_id` field
- Properly linked to KB: `fdb42d38-892d-48e8-bc4e-1f92452dbc7d`

**Knowledge Base Summary:**
```sql
SELECT kb.id, kb.name, kb.owner_username, COUNT(c.id) as cluster_count
FROM knowledge_bases kb
LEFT JOIN clusters c ON kb.id = c.knowledge_base_id
GROUP BY kb.id;
```

**Results:**
```
                  id                  |        name         | owner_username | cluster_count
--------------------------------------+---------------------+----------------+---------------
 fdb42d38-892d-48e8-bc4e-1f92452dbc7d | Main Knowledge Base | daz2208        |             5
```

---

### ✅ 2. In-Memory Structure - CORRECT
**File:** `backend/dependencies.py` (Lines 41-45)

```python
# Document storage (in-memory) - nested by knowledge_base_id
# Structure: {kb_id: {doc_id: content/metadata/cluster}}
documents: Dict[str, Dict[int, str]] = {}
metadata: Dict[str, Dict[int, DocumentMetadata]] = {}
clusters: Dict[str, Dict[int, Cluster]] = {}
users: Dict[str, str] = {}  # username -> hashed_password
```

**Status:** ✅ **Structure is correctly nested**
- Outer key: `kb_id` (UUID string)
- Inner dict: `{doc_id: data}` or `{cluster_id: Cluster}`
- Proper separation by knowledge base

---

### ✅ 3. KB-Scoped Access Functions - CORRECT
**File:** `backend/dependencies.py` (Lines 165-184)

```python
def get_kb_clusters(kb_id: str) -> Dict[int, Cluster]:
    """Get clusters for a specific knowledge base."""
    if kb_id not in clusters:
        clusters[kb_id] = {}
    return clusters[kb_id]

def get_kb_documents(kb_id: str) -> Dict[int, str]:
    """Get documents for a specific knowledge base."""
    if kb_id not in documents:
        documents[kb_id] = {}
    return documents[kb_id]

def get_kb_metadata(kb_id: str) -> Dict[int, DocumentMetadata]:
    """Get metadata for a specific knowledge base."""
    if kb_id not in metadata:
        metadata[kb_id] = {}
    return metadata[kb_id]

def ensure_kb_exists(kb_id: str) -> None:
    """Ensure knowledge base exists in all dictionaries."""
    if kb_id not in documents:
        documents[kb_id] = {}
    if kb_id not in metadata:
        metadata[kb_id] = {}
    if kb_id not in clusters:
        clusters[kb_id] = {}
```

**Status:** ✅ **Functions correctly filter by KB ID**
- Returns only data for specified KB
- Creates empty dict if KB doesn't exist
- Proper encapsulation

---

### ✅ 4. Search Endpoint - CORRECT IMPLEMENTATION
**File:** `backend/routers/search.py` (Lines 96-101)

```python
# Get user's default KB ID
kb_id = get_user_default_kb_id(current_user.username, db)

# Get KB-scoped storage
kb_documents = get_kb_documents(kb_id)
kb_metadata = get_kb_metadata(kb_id)
kb_clusters = get_kb_clusters(kb_id)
vector_store = get_vector_store()
```

**Status:** ✅ **Search correctly uses KB separation**
1. Gets user's default KB ID from database
2. Uses `get_kb_documents(kb_id)` to get ONLY that KB's documents
3. Uses `get_kb_metadata(kb_id)` to get ONLY that KB's metadata
4. Uses `get_kb_clusters(kb_id)` to get ONLY that KB's clusters
5. Then filters by username within that KB

**This is the CORRECT pattern!**

---

### 🐛 5. Build Suggestions Endpoint - INCORRECT IMPLEMENTATION
**File:** `backend/routers/build_suggestions.py` (Lines 61-101)

```python
# WRONG: Gets ALL data from ALL KBs
documents = get_documents()
metadata = get_metadata()
clusters = get_clusters()
build_suggester = get_build_suggester()

# Validate max_suggestions parameter
max_suggestions = validate_positive_integer(req.max_suggestions, "max_suggestions", max_value=MAX_SUGGESTIONS)
if max_suggestions < 1:
    max_suggestions = 5

# WRONG: Flattens ALL KBs together (data mixing!)
# clusters: Dict[str, Dict[int, Cluster]] -> Dict[int, Cluster]
all_clusters = {}
for kb_id, kb_clusters in clusters.items():
    all_clusters.update(kb_clusters)  # ⚠️ MIXING ALL KBS!

# metadata: Dict[str, Dict[int, DocumentMetadata]] -> Dict[int, DocumentMetadata]
all_metadata = {}
for kb_id, kb_metadata in metadata.items():
    all_metadata.update(kb_metadata)  # ⚠️ MIXING ALL KBS!

# documents: Dict[str, Dict[int, str]] -> Dict[int, str]
all_documents = {}
for kb_id, kb_documents in documents.items():
    all_documents.update(kb_documents)  # ⚠️ MIXING ALL KBS!

# Filter to user's content (but already mixed!)
user_clusters = {
    cid: cluster for cid, cluster in all_clusters.items()
    if any(all_metadata.get(did) and all_metadata[did].owner == current_user.username for did in cluster.doc_ids)
}

user_metadata = {
    did: meta for did, meta in all_metadata.items()
    if meta.owner == current_user.username
}

user_documents = {
    did: doc for did, doc in all_documents.items()
    if did in user_metadata
}
```

**Status:** 🐛 **BROKEN - Mixing data from all KBs**

---

## The Problem

### What's Happening
1. **Line 61-63:** Gets ALL documents/metadata/clusters from ALL knowledge bases
2. **Lines 71-85:** Flattens them into single dictionaries, **mixing all KBs together**
3. **Lines 87-101:** Filters by username, but data is already mixed

### Why This is Dangerous

#### Issue 1: Document ID Collisions
```python
# KB 1 (User A):
documents['kb-1'][0] = "User A's document 0"
documents['kb-1'][1] = "User A's document 1"

# KB 2 (User B):
documents['kb-2'][0] = "User B's document 0"  # ⚠️ Same ID!
documents['kb-2'][1] = "User B's document 1"  # ⚠️ Same ID!

# After flattening (WRONG!):
all_documents = {
    0: "User B's document 0",  # ❌ Overwrote User A's doc!
    1: "User B's document 1"   # ❌ Overwrote User A's doc!
}
# User A's documents are LOST!
```

**Result:** If document IDs overlap between KBs, later KBs overwrite earlier ones.

#### Issue 2: Incorrect Cluster Attribution
```python
# Cluster 0 in KB-1 might refer to doc_ids [0, 1, 2]
# Cluster 0 in KB-2 might also refer to doc_ids [0, 1, 2]
# After mixing, which documents does Cluster 0 refer to?
# Answer: WRONG ONES!
```

#### Issue 3: Data Leakage
```python
# User A in KB-1 has document 5
# User B in KB-2 also has document 5
# After flattening, only one survives
# When filtering by username, might get wrong document!
```

---

## Root Cause Analysis

### Why Was This Done?
Looking at the code comments:
```python
# Flatten nested structures (all are nested by kb_id)
# clusters: Dict[str, Dict[int, Cluster]] -> Dict[int, Cluster]
```

This was my fix from earlier today to resolve the `AttributeError: 'dict' object has no attribute 'doc_ids'` bug. The original code was trying to access `cluster.doc_ids` directly on the nested structure, which failed.

**My fix was WRONG!** I should have:
1. Used KB-scoped functions like search does
2. Got the user's default KB ID first
3. Accessed only that KB's data

**Instead, I flattened everything together, which "fixed" the immediate error but created this data isolation bug.**

---

## Correct Implementation

### What Search Does (CORRECT)
```python
# 1. Get user's KB ID
kb_id = get_user_default_kb_id(current_user.username, db)

# 2. Get ONLY that KB's data
kb_documents = get_kb_documents(kb_id)
kb_metadata = get_kb_metadata(kb_id)
kb_clusters = get_kb_clusters(kb_id)

# 3. Filter by username WITHIN that KB
user_doc_ids = [
    doc_id for doc_id, meta in kb_metadata.items()
    if meta.owner == current_user.username
]
```

### What Build Suggestions Should Do (FIX NEEDED)
```python
# 1. Import DB dependency
from ..database import get_db
from sqlalchemy.orm import Session

# 2. Add db parameter to endpoint
async def what_can_i_build(
    req: BuildSuggestionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)  # NEW: Add database session
):
    # 3. Get user's KB ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # 4. Get KB-scoped data (NOT flattened!)
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    build_suggester = get_build_suggester()

    # 5. Filter by username WITHIN that KB
    user_clusters = {
        cid: cluster for cid, cluster in kb_clusters.items()
        if any(kb_metadata.get(did) and kb_metadata[did].owner == current_user.username for did in cluster.doc_ids)
    }

    user_metadata = {
        did: meta for did, meta in kb_metadata.items()
        if meta.owner == current_user.username
    }

    user_documents = {
        did: doc for did, doc in kb_documents.items()
        if did in user_metadata
    }

    # Rest of the code remains the same...
```

---

## Impact Assessment

### Current Impact (Single User System)
**Risk Level:** 🟡 **LOW** (Currently only 1 user, 1 KB)

With only one user and one KB:
- No data collision yet
- No data leakage yet
- Functionally works correctly

### Future Impact (Multi-User System)
**Risk Level:** 🔴 **CRITICAL**

When multiple users have multiple KBs:
- ❌ **Data collisions** - Documents with same IDs overwrite each other
- ❌ **Data leakage** - Users could see wrong documents
- ❌ **Incorrect suggestions** - Build suggestions based on wrong data
- ❌ **Broken clusters** - Cluster doc_ids point to wrong documents
- ❌ **Security issue** - User A might get User B's data

---

## Testing Proof

### Test 1: Verify Current KB Count
```sql
SELECT COUNT(*) FROM knowledge_bases;
-- Result: 1 (only daz2208's KB)
```
✅ **Currently safe because only 1 KB exists**

### Test 2: Simulate Multi-KB Scenario
```python
# Hypothetical scenario:
clusters = {
    'kb-1': {0: Cluster(id=0, doc_ids=[0, 1])},
    'kb-2': {0: Cluster(id=0, doc_ids=[2, 3])}
}

# After flattening (current buggy code):
all_clusters = {}
for kb_id, kb_clusters in clusters.items():
    all_clusters.update(kb_clusters)

print(all_clusters)
# Output: {0: Cluster(id=0, doc_ids=[2, 3])}
# ❌ KB-1's cluster is LOST!
```

---

## Other Affected Endpoints?

Let me check if other endpoints have the same issue:

### ✅ Search Endpoint - CORRECT
**File:** `backend/routers/search.py`
- Uses `get_user_default_kb_id()`
- Uses `get_kb_documents()`, `get_kb_metadata()`, `get_kb_clusters()`
- Properly isolated by KB

### 🔍 Clusters Endpoint - NEEDS CHECK
**File:** `backend/routers/clusters.py`
- May have similar issue

### 🔍 Documents Endpoint - NEEDS CHECK
**File:** `backend/routers/documents.py`
- May have similar issue

### 🔍 Analytics Endpoint - NEEDS CHECK
**File:** `backend/routers/analytics.py`
- May have similar issue

### 🔍 AI Generation Endpoint - NEEDS CHECK
**File:** `backend/routers/ai_generation.py`
- May have similar issue

---

## Recommended Fix Priority

### Priority 1: Fix Build Suggestions (IMMEDIATE)
**File:** `backend/routers/build_suggestions.py`
**Lines:** 61-101
**Action:** Replace flattening with KB-scoped access

### Priority 2: Audit All Endpoints (URGENT)
**Check each endpoint for:**
- Use of `get_documents()` instead of `get_kb_documents(kb_id)`
- Use of `get_metadata()` instead of `get_kb_metadata(kb_id)`
- Use of `get_clusters()` instead of `get_kb_clusters(kb_id)`
- Missing `get_user_default_kb_id()` calls

### Priority 3: Add Tests (HIGH)
**Create tests to verify:**
- Multi-KB data isolation
- Document ID collision prevention
- Correct filtering by KB + username

### Priority 4: Add Validation (MEDIUM)
**Add runtime checks:**
- Warn if duplicate doc IDs across KBs
- Log KB IDs in all operations
- Assert KB isolation in development

---

## Fix Implementation Plan

### Step 1: Import Dependencies
```python
from ..database import get_db
from sqlalchemy.orm import Session
from ..dependencies import (
    get_user_default_kb_id,  # NEW
    get_kb_documents,         # NEW
    get_kb_metadata,          # NEW
    get_kb_clusters,          # NEW
    get_build_suggester,
)
```

### Step 2: Update Endpoint Signature
```python
async def what_can_i_build(
    req: BuildSuggestionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)  # NEW
):
```

### Step 3: Replace Flattening with KB-Scoped Access
```python
# OLD (WRONG):
documents = get_documents()
metadata = get_metadata()
clusters = get_clusters()
all_clusters = {}
for kb_id, kb_clusters in clusters.items():
    all_clusters.update(kb_clusters)
# ... flatten everything ...

# NEW (CORRECT):
kb_id = get_user_default_kb_id(current_user.username, db)
kb_documents = get_kb_documents(kb_id)
kb_metadata = get_kb_metadata(kb_id)
kb_clusters = get_kb_clusters(kb_id)
```

### Step 4: Update Filtering Logic
```python
# Filter to user's content (within their KB)
user_clusters = {
    cid: cluster for cid, cluster in kb_clusters.items()
    if any(kb_metadata.get(did) and kb_metadata[did].owner == current_user.username for did in cluster.doc_ids)
}

user_metadata = {
    did: meta for did, meta in kb_metadata.items()
    if meta.owner == current_user.username
}

user_documents = {
    did: doc for did, doc in kb_documents.items()
    if did in user_metadata
}
```

---

## Prevention Measures

### Code Review Checklist
When adding/modifying endpoints:
- [ ] Uses `get_user_default_kb_id()` to get KB ID
- [ ] Uses `get_kb_documents(kb_id)` not `get_documents()`
- [ ] Uses `get_kb_metadata(kb_id)` not `get_metadata()`
- [ ] Uses `get_kb_clusters(kb_id)` not `get_clusters()`
- [ ] Never flattens nested KB structures
- [ ] Filters by username AFTER KB filtering

### Documentation
- Add KB separation guidelines to CLAUDE.md
- Document correct pattern in architecture docs
- Add examples of correct vs incorrect patterns

### Testing
- Add integration tests for multi-KB scenarios
- Test document ID collisions
- Test data isolation between users
- Test data isolation between KBs

---

## Lessons Learned

### What Went Wrong
1. **Quick Fix Mentality:** Fixed the immediate error without understanding root cause
2. **Pattern Breaking:** Broke the established KB separation pattern
3. **No Testing:** Didn't test with multi-KB scenario
4. **No Code Review:** Existing endpoint (search.py) had correct pattern

### What Should Have Been Done
1. **Pattern Matching:** Check how other endpoints handle KB data
2. **Root Cause Analysis:** Understand why nested structure exists
3. **Test Coverage:** Test with multiple KBs and users
4. **Documentation Check:** Read CLAUDE.md for architecture patterns

---

## Summary

### The Bug
Build suggestions endpoint mixes data from all knowledge bases together, then filters by username. This breaks KB isolation and can cause data collisions.

### The Risk
- **Current:** Low (only 1 KB exists)
- **Future:** Critical (multi-KB/multi-user scenarios)

### The Fix
Replace global data access + flattening with KB-scoped access (same pattern as search endpoint).

### The Lesson
When in doubt, **follow existing patterns** in the codebase. Search endpoint had the correct implementation all along.

---

**Bug Status:** 🐛 **CONFIRMED - FIX REQUIRED**
**Fix Complexity:** ⭐⭐☆☆☆ (Simple - copy pattern from search.py)
**Test Priority:** 🔴 **HIGH** (Add multi-KB tests)

---

*This bug was discovered during investigation of KB separation requested by user daz2208 on 2025-11-19.*
