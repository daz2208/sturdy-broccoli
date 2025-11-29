# Unused Code Audit - Global State & Legacy Storage

**Date**: 2025-11-29
**Status**: Repository Pattern Migration Complete
**Purpose**: Identify code that can be safely removed after migration

---

## 1. GLOBAL STATE DICTIONARIES (dependencies.py)

### Declared (lines 50-53):
```python
documents: Dict[str, Dict[int, str]] = {}
metadata: Dict[str, Dict[int, DocumentMetadata]] = {}
clusters: Dict[str, Dict[int, Cluster]] = {}
users: Dict[str, str] = {}
```

### Direct Usage Analysis:

**STILL USED** - These are populated by `load_storage_from_db()` for backwards compatibility:
- `main.py` lines 100, 166: Loads from DB into global dicts on startup
- `tasks.py` line 133: Reloads cache from DB into global dicts
- All helper functions in `dependencies.py` return references to these

### Helper Functions Using Global State:

#### KB-Scoped Helpers (STILL USED):
- `get_kb_documents(kb_id)` - Used by 3 routers (knowledge_bases, n8n_workflows, relationships)
- `get_kb_metadata(kb_id)` - Used by 3 routers
- `get_kb_clusters(kb_id)` - Used by 2 routers

#### Global Helpers (USED):
- `get_documents()` - Used in relationships.py:149
- `get_metadata()` - Used in some routers
- `get_clusters()` - Used in some routers
- `get_users()` - No longer used (removed from auth.py)

---

## 2. STORAGE LOCK (dependencies.py)

### Declared (line 56):
```python
storage_lock = asyncio.Lock()
```

### Usage:
- ❓ **UNCLEAR** - Need to verify if still used for vector_store operations
- Repository has its own async lock for DB operations
- Vector store may still use this for in-memory operations

**ACTION NEEDED**: Grep for `storage_lock` usage

---

## 3. FILE STORAGE (storage.json)

### File Location:
```
./storage.json
```

### Usage:
- ❌ **NOT USED ANYMORE** - Replaced by PostgreSQL
- May still exist from old deployments
- `load_storage()` function in `file_storage.py` loads this as fallback

**SAFE TO DELETE**: ✅ Yes, if PostgreSQL is primary

---

## 4. DB_STORAGE_ADAPTER.PY

### Functions Declared:

#### `save_storage_to_db(documents, metadata, clusters, users)`
**Usage Count**: 0
**Status**: ❌ **REMOVED** - All removed during migration
**Action**: Can delete this function

#### `load_storage_from_db(vector_store)`
**Usage Count**: 3
**Status**: ✅ **STILL USED**
**Locations**:
- `main.py:100` - Startup: Load DB → global state
- `main.py:166` - Startup fallback
- `tasks.py:133` - reload_cache_from_db()

**Purpose**: Populates global state dicts from database
**Action**: Keep for now (backwards compat cache)

---

## 5. FILE_STORAGE.PY

### Functions:

#### `load_storage(path, vector_store)`
**Usage**: Fallback in main.py:181 if DB load fails
**Status**: ⚠️ **FALLBACK ONLY**
**Action**: Keep for backwards compatibility

#### `save_storage(path, documents, metadata, clusters, users)`
**Usage**: ❓ Need to check
**Status**: Likely unused
**Action**: Audit needed

---

## 6. HELPER FUNCTIONS IN DEPENDENCIES.PY

### Backwards Compatibility Helpers (STILL USED):

```python
# Line 224-264: KB-scoped access helpers
get_kb_documents(kb_id)    # ✅ Used by 3 routers
get_kb_metadata(kb_id)     # ✅ Used by 3 routers
get_kb_clusters(kb_id)     # ✅ Used by 2 routers
```

**Why Still Used**:
- `find_or_create_cluster()` function needs these
- Some routers still reference global state for read-only operations
- Backwards compatibility during gradual migration

### Direct Access Helpers (MOSTLY UNUSED):

```python
get_documents()    # ⚠️ Used in 1 place (relationships.py:149)
get_metadata()     # ⚠️ Used in some routers
get_clusters()     # ⚠️ Used in some routers
get_users()        # ❌ REMOVED from auth.py (migration complete)
```

---

## 7. FINDINGS SUMMARY

### ✅ **CAN SAFELY DELETE**:

1. **`save_storage_to_db()` function** in `db_storage_adapter.py`
   - 0 usages remain
   - Fully replaced by repository pattern

2. **`storage.json` file** (if it exists)
   - No longer written to
   - PostgreSQL is source of truth

3. **`get_users()` helper** (debatable)
   - No longer imported by auth.py
   - May have other usages to check

### ⚠️ **KEEP FOR NOW** (Backwards Compatibility):

1. **Global state dicts** (documents, metadata, clusters, users)
   - Still populated from DB as read cache
   - Used by helper functions
   - Used by some routers for read operations

2. **`load_storage_from_db()` function**
   - Used to populate cache on startup
   - Used by reload_cache_from_db()
   - Critical for backwards compatibility

3. **KB-scoped helpers** (get_kb_documents, get_kb_metadata, get_kb_clusters)
   - Actively used by 3+ routers
   - Used by find_or_create_cluster()
   - Part of KB isolation security

4. **`file_storage.py`**
   - Fallback mechanism
   - May be needed for migrations

### ❓ **NEED INVESTIGATION**:

1. **`storage_lock`** - Check if still needed for vector_store
2. **`save_storage()` in file_storage.py** - Check usage count
3. **Direct access helpers** - Verify all usages and if can replace with repository

---

## 8. RECOMMENDED CLEANUP PHASES

### Phase 1: Safe Deletions (Do Now)
1. Delete `save_storage_to_db()` from `db_storage_adapter.py`
2. Remove unused import from `main.py` line 62
3. Delete `storage.json` file if exists
4. Remove `get_users()` helper if no other usages

### Phase 2: Migration Tasks (Future)
1. Migrate remaining routers to use repository exclusively
2. Remove dependency on global state for read operations
3. Replace KB-scoped helpers with repository methods
4. Remove `load_storage_from_db()` once cache is removed

### Phase 3: Final Cleanup (Future)
1. Delete global state dicts entirely
2. Delete `db_storage_adapter.py` completely
3. Delete `file_storage.py` (or mark deprecated)
4. Delete `storage_lock` if vector_store doesn't need it

---

## 9. VERIFICATION COMMANDS

```bash
# Check save_storage_to_db usage
grep -rn "save_storage_to_db" backend/ --include="*.py" | grep -v "db_storage_adapter.py"

# Check load_storage_from_db usage
grep -rn "load_storage_from_db" backend/ --include="*.py" | grep -v "db_storage_adapter.py"

# Check global state helpers usage
grep -rn "get_kb_documents\|get_kb_metadata\|get_kb_clusters" backend/routers/ --include="*.py"

# Check storage_lock usage
grep -rn "storage_lock" backend/ --include="*.py"

# Check if storage.json exists
ls -la storage.json
```

---

## 10. RISK ASSESSMENT

**Low Risk (Safe to delete now)**:
- ✅ save_storage_to_db() - Already verified 0 usages
- ✅ storage.json file - Not written to anymore
- ✅ Unused imports

**Medium Risk (Verify first)**:
- ⚠️ storage_lock - May affect vector_store thread safety
- ⚠️ get_users() - May have usages outside auth
- ⚠️ file_storage.py functions - Need usage audit

**High Risk (Don't delete yet)**:
- ❌ Global state dicts - Still actively used as cache
- ❌ load_storage_from_db() - Critical for startup
- ❌ KB-scoped helpers - Used by multiple routers

---

**END OF AUDIT**
