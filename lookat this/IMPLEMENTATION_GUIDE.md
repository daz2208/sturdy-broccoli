# Knowledge Base Architecture Implementation Guide

## What You're Getting

1. ✅ **Multi-knowledge-base support** - Separate "brains" for different topics
2. ✅ **Build suggestion persistence** - Save and track project suggestions
3. ✅ **No more content contamination** - Dev docs won't pollute farming research
4. ✅ **Full history** - All suggestions saved, can mark as completed

---

## Files I Created For You

### 1. `migration_add_knowledge_bases.py`
- Alembic migration to add knowledge base tables
- Automatically creates default knowledge base for existing users
- Migrates all existing documents to default base

### 2. `db_models_additions.py`
- SQLAlchemy models for `DBKnowledgeBase` and `DBBuildSuggestion`
- Instructions for updating existing `DBDocument` and `DBCluster` models

### 3. `pydantic_models_additions.py`
- Pydantic models for API validation
- Request/response schemas for knowledge bases

### 4. `knowledge_bases_router.py`
- Complete FastAPI router with all endpoints
- CRUD operations for knowledge bases
- Generate and manage build suggestions

---

## Installation Steps

### Phase 1: Update Database Models (10 min)

**File: `backend/db_models.py`**

1. Add the two new model classes from `db_models_additions.py`:
   - `DBKnowledgeBase`
   - `DBBuildSuggestion`

2. Update existing `DBDocument` class - add these two lines:
```python
knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
knowledge_base = relationship("DBKnowledgeBase", back_populates="documents")
```

3. Update existing `DBCluster` class - add these two lines:
```python
knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
knowledge_base = relationship("DBKnowledgeBase", back_populates="clusters")
```

### Phase 2: Update Pydantic Models (5 min)

**File: `backend/models.py`**

1. Add all the new models from `pydantic_models_additions.py`

2. Update existing `DocumentMetadata` class - add:
```python
knowledge_base_id: str = Field(..., description="Knowledge base ID")
```

### Phase 3: Run Migration (2 min)

```powershell
# Copy migration file
cp migration_add_knowledge_bases.py refactored/syncboard_backend/alembic/versions/

# Rename it with timestamp
# Example: kb001_20251119_knowledge_bases.py

# Run migration
cd refactored/syncboard_backend
docker-compose exec backend alembic upgrade head

# Or if not using Docker:
alembic upgrade head
```

### Phase 4: Add Router (5 min)

```powershell
# Copy router file
cp knowledge_bases_router.py refactored/syncboard_backend/backend/routers/

# Update main.py to include the router
```

**In `backend/main.py`, add:**
```python
from .routers import knowledge_bases

app.include_router(knowledge_bases.router)
```

### Phase 5: Update Dependencies (15 min)

**File: `backend/dependencies.py`**

The in-memory cache needs to be restructured:

**OLD:**
```python
documents: Dict[int, str] = {}
metadata: Dict[int, DocumentMetadata] = {}
clusters: Dict[int, Cluster] = {}
```

**NEW:**
```python
documents: Dict[str, Dict[int, str]] = {}  # {kb_id: {doc_id: content}}
metadata: Dict[str, Dict[int, DocumentMetadata]] = {}  # {kb_id: {doc_id: meta}}
clusters: Dict[str, Dict[int, Cluster]] = {}  # {kb_id: {cluster_id: cluster}}
```

### Phase 6: Update All Endpoints (30-45 min)

Every endpoint that accesses documents/clusters needs to be scoped by `knowledge_base_id`.

**Example pattern:**

**Before:**
```python
@router.post("/upload_text")
async def upload_text(text: str, current_user: User = Depends(get_current_user)):
    doc_id = dependencies.vector_store.add_document(text)
    dependencies.documents[doc_id] = text
```

**After:**
```python
@router.post("/upload_text")
async def upload_text(
    text: str,
    knowledge_base_id: str,  # Add this parameter
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify KB ownership
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == knowledge_base_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()
    if not kb:
        raise HTTPException(404, "Knowledge base not found")
    
    # Scope by KB
    if knowledge_base_id not in dependencies.documents:
        dependencies.documents[knowledge_base_id] = {}
    
    doc_id = dependencies.vector_store.add_document(text)
    dependencies.documents[knowledge_base_id][doc_id] = text
```

**Endpoints to update:**
- `/upload_text`
- `/upload_*` (all upload endpoints)
- `/search_full`
- `/clusters`
- `/what_can_i_build`
- `/analytics`

### Phase 7: Update Build Suggester (10 min)

**File: `backend/build_suggester_improved.py`**

No changes needed! Just update how you call it:

**Before:**
```python
suggestions = await suggester.analyze_knowledge_bank(
    clusters=dependencies.clusters,
    metadata=dependencies.metadata,
    documents=dependencies.documents
)
```

**After:**
```python
# Filter by KB first
kb_clusters = dependencies.clusters.get(kb_id, {})
kb_metadata = dependencies.metadata.get(kb_id, {})
kb_documents = dependencies.documents.get(kb_id, {})

suggestions = await suggester.analyze_knowledge_bank(
    clusters=kb_clusters,
    metadata=kb_metadata,
    documents=kb_documents
)
```

---

## Testing

### 1. Create Knowledge Base
```bash
curl -X POST http://localhost:8000/knowledge-bases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Dev Projects", "description": "My development work"}'
```

### 2. Upload Content
```bash
curl -X POST http://localhost:8000/upload_text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "FastAPI tutorial...", "knowledge_base_id": "your-kb-id"}'
```

### 3. Generate Suggestions
```bash
curl -X POST http://localhost:8000/knowledge-bases/{kb_id}/suggestions/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"knowledge_base_id": "your-kb-id", "max_suggestions": 5}'
```

### 4. List Suggestions
```bash
curl http://localhost:8000/knowledge-bases/{kb_id}/suggestions \
  -H "Authorization: Bearer $TOKEN"
```

---

## Frontend Integration (Future)

You'll need to add:

1. **Knowledge Base Selector** - Dropdown in nav bar
2. **Create KB Button** - Modal to create new bases
3. **Suggestions View** - Page to see saved suggestions with "Mark Complete" buttons

---

## Migration Notes

- All existing documents will be moved to "Main Knowledge Base"
- No data loss
- Can roll back with `alembic downgrade -1`
- Database size will increase slightly (new tables)

---

## Time Estimate

- Database updates: 15 min
- Migration: 5 min
- Router integration: 5 min
- Dependencies update: 20 min
- Endpoint updates: 1-2 hours
- Testing: 30 min

**Total: 2-3 hours**

---

## What Works After Implementation

✅ Multiple isolated knowledge bases
✅ No content contamination between bases
✅ Build suggestions saved to database
✅ Can mark suggestions as completed
✅ Full history of all suggestions
✅ Per-base analytics
✅ Easy to delete/rename bases

---

## Need Help?

If you hit issues:
1. Check logs: `docker logs syncboard-backend`
2. Verify migration: `alembic current`
3. Check DB: `psql -U syncboard -d syncboard -c "SELECT * FROM knowledge_bases;"`

The router I created has comprehensive error handling, so you'll get clear error messages if something's wrong.
