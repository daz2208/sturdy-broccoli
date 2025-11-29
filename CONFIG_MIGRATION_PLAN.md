# Config Migration Plan - os.getenv() to Pydantic Settings

**Date:** 2025-11-29
**Goal:** Migrate all 64 `os.getenv()` calls to use centralized `settings` object
**Approach:** Careful, file-by-file migration with testing

---

## 📋 Pre-Migration Checklist

- [x] Audit complete - 64 instances identified
- [x] config.py reviewed - comprehensive Pydantic Settings ready
- [x] Backup strategy - Git branch for rollback
- [ ] Migration execution
- [ ] Testing validation
- [ ] Commit and push

---

## 🎯 Migration Strategy

### Phase 1: Large Files (High Impact)
1. `routers/integrations.py` - 18 calls (OAuth configs)
2. `routers/auth.py` - 8 calls (OAuth, testing)
3. `routers/admin.py` - 7 calls (LLM configs)

### Phase 2: Core Services
4. `llm_providers.py` - 5 calls (OpenAI, Ollama)
5. `ingest.py` - 4 calls (transcription, API keys)
6. `routers/build_suggestions.py` - 4 calls (API keys)

### Phase 3: Smaller Files (Cleanup)
7. `utils/encryption.py` - 5 calls (encryption key)
8. `concept_extractor.py` - 2 calls (API key)
9. `enhanced_rag.py` - 2 calls (API key)
10. `cache.py` - 1 call (Redis URL)
11. `embedding_service.py` - 1 call (API key)
12. `summarization_service.py` - 2 calls (API key, model)
13. `image_processor.py` - 1 call (Tesseract)
14. `idea_seeds_service.py` - 2 calls (API key, model)
15. `ai_generation_real.py` - 1 call (API key)
16. `knowledge_services.py` - 1 call (API key)
17. `routers/n8n_workflows.py` - 1 call (API key)
18. `models.py` - 1 call (MAX_BATCH_FILES)

---

## 🔍 Detailed File Analysis

### 1. routers/integrations.py (18 calls)

**Current Usage:**
```python
os.getenv("GITHUB_CLIENT_ID", "")
os.getenv("GITHUB_CLIENT_SECRET", "")
os.getenv("GITHUB_REDIRECT_URI", "http://...")
os.getenv("GOOGLE_CLIENT_ID", "")
os.getenv("GOOGLE_CLIENT_SECRET", "")
os.getenv("GOOGLE_REDIRECT_URI", "http://...")
os.getenv("DROPBOX_APP_KEY", "")
os.getenv("DROPBOX_APP_SECRET", "")
os.getenv("DROPBOX_REDIRECT_URI", "http://...")
os.getenv("NOTION_CLIENT_ID", "")
os.getenv("NOTION_CLIENT_SECRET", "")
os.getenv("NOTION_REDIRECT_URI", "http://...")
```

**Migration:**
```python
from backend.config import settings

settings.github_client_id
settings.github_client_secret
settings.github_redirect_uri
# ... etc
```

**Risk:** LOW - All fields already defined in config.py
**Testing:** Verify OAuth flows still work

---

### 2. routers/auth.py (8 calls)

**Current Usage:**
```python
TESTING = os.environ.get('TESTING') == 'true'
os.getenv("GOOGLE_CLIENT_ID", "")
os.getenv("GOOGLE_CLIENT_SECRET", "")
os.getenv("OAUTH_GOOGLE_REDIRECT_URI", "...")
os.getenv("GITHUB_CLIENT_ID", "")
os.getenv("GITHUB_CLIENT_SECRET", "")
os.getenv("OAUTH_GITHUB_REDIRECT_URI", "...")
os.getenv("FRONTEND_URL", "http://localhost:3000")
```

**Migration:**
```python
from backend.config import settings

settings.is_testing  # or settings.testing
settings.google_client_id
settings.frontend_url
# ... etc
```

**Risk:** LOW - All fields exist in config.py
**Testing:** Verify login/register flows

---

### 3. routers/admin.py (7 calls)

**Current Usage:**
```python
os.environ.get("LLM_PROVIDER", "openai")
os.environ.get("OPENAI_API_KEY", "")
os.environ.get("OPENAI_CONCEPT_MODEL", "gpt-5-nano")
os.environ.get("OPENAI_SUGGESTION_MODEL", "gpt-5-mini")
os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.get("OLLAMA_CONCEPT_MODEL", "llama2")
os.environ.get("OLLAMA_SUGGESTION_MODEL", "llama2")
```

**Migration:**
```python
from backend.config import settings

settings.llm_provider
settings.openai_api_key
settings.openai_concept_model
settings.openai_suggestion_model
settings.ollama_base_url
# ... etc
```

**Risk:** LOW - All fields exist
**Testing:** Verify admin endpoints return correct config

---

### 4. llm_providers.py (5 calls)

**Current Usage:**
```python
api_key or os.environ.get("OPENAI_API_KEY")
os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.get("OLLAMA_CONCEPT_MODEL", "llama2")
os.environ.get("OLLAMA_SUGGESTION_MODEL", "llama2")
os.environ.get("LLM_PROVIDER", "openai")
```

**Migration:**
```python
from backend.config import settings

api_key or settings.openai_api_key
settings.ollama_base_url
settings.ollama_concept_model
settings.ollama_suggestion_model
settings.llm_provider
```

**Risk:** MEDIUM - Core LLM functionality
**Testing:** Verify concept extraction, build suggestions work

---

### 5. ingest.py (4 calls)

**Current Usage:**
```python
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TRANSCRIPTION_MODEL = os.environ.get("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
CHUNK_DURATION_SECONDS = int(os.environ.get("TRANSCRIPTION_CHUNK_DURATION_SECONDS", "300"))
CHUNK_DURATION_THRESHOLD_SECONDS = int(os.environ.get("TRANSCRIPTION_CHUNK_THRESHOLD_SECONDS", "600"))
```

**Migration:**
```python
from backend.config import settings

OPENAI_API_KEY = settings.openai_api_key
TRANSCRIPTION_MODEL = settings.transcription_model
CHUNK_DURATION_SECONDS = settings.transcription_chunk_duration_seconds
CHUNK_DURATION_THRESHOLD_SECONDS = settings.transcription_chunk_threshold_seconds
```

**Risk:** MEDIUM - Ingestion pipeline is critical
**Testing:** Verify YouTube transcription, file uploads work

---

### 6. routers/build_suggestions.py (4 calls)

**Current Usage:**
```python
api_key = os.getenv("OPENAI_API_KEY")  # 3 times
```

**Migration:**
```python
from backend.config import settings

api_key = settings.openai_api_key
```

**Risk:** LOW - Simple API key access
**Testing:** Verify build suggestion generation

---

### 7-18. Remaining Files (1-2 calls each)

**Pattern:**
- Most are simple `os.getenv("OPENAI_API_KEY")` → `settings.openai_api_key`
- Some are model names, Redis URLs, encryption keys
- All have corresponding fields in config.py

**Risk:** LOW - Single-line changes
**Testing:** Spot-check critical paths

---

## 🧪 Testing Strategy

### 1. Per-File Testing
After each file migration:
- [ ] Check syntax (Python imports)
- [ ] Verify no AttributeError on settings access
- [ ] Run specific tests for that module (if available)

### 2. Integration Testing
After all migrations:
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Check critical paths:
  - [ ] User registration/login
  - [ ] Document upload (text, file, URL)
  - [ ] Search functionality
  - [ ] Build suggestion generation
  - [ ] OAuth flows

### 3. Smoke Testing
- [ ] Start server: `uvicorn backend.main:app --reload`
- [ ] Check startup logs for errors
- [ ] Test one API call from each major router

---

## 🚨 Risk Mitigation

### Backup Strategy
- ✅ Git branch: `claude/review-and-document-updates-012EoXFTh6rWY6uUvJkNe5fn`
- ✅ Can revert with `git checkout -- <file>` if needed

### Rollback Plan
If migration causes issues:
1. Identify failing file
2. Revert specific file: `git checkout HEAD -- backend/<file>.py`
3. Fix issue
4. Re-apply migration

### Safety Measures
1. **One file at a time** - Don't batch all changes
2. **Test after each file** - Catch issues early
3. **Document changes** - Clear commit messages
4. **Verify imports** - Ensure `settings` is imported

---

## 📝 Migration Checklist

### Phase 1: Large Files
- [ ] Migrate routers/integrations.py (18 calls)
- [ ] Test OAuth integrations
- [ ] Migrate routers/auth.py (8 calls)
- [ ] Test login/register
- [ ] Migrate routers/admin.py (7 calls)
- [ ] Test admin endpoints

### Phase 2: Core Services
- [ ] Migrate llm_providers.py (5 calls)
- [ ] Test concept extraction
- [ ] Migrate ingest.py (4 calls)
- [ ] Test document upload
- [ ] Migrate routers/build_suggestions.py (4 calls)
- [ ] Test build suggestions

### Phase 3: Cleanup
- [ ] Migrate utils/encryption.py (5 calls)
- [ ] Migrate concept_extractor.py (2 calls)
- [ ] Migrate enhanced_rag.py (2 calls)
- [ ] Migrate summarization_service.py (2 calls)
- [ ] Migrate idea_seeds_service.py (2 calls)
- [ ] Migrate cache.py (1 call)
- [ ] Migrate embedding_service.py (1 call)
- [ ] Migrate image_processor.py (1 call)
- [ ] Migrate ai_generation_real.py (1 call)
- [ ] Migrate knowledge_services.py (1 call)
- [ ] Migrate routers/n8n_workflows.py (1 call)
- [ ] Migrate models.py (1 call)

### Final Steps
- [ ] Run full test suite
- [ ] Check for any remaining os.getenv() calls
- [ ] Update documentation
- [ ] Commit changes
- [ ] Push to remote

---

## ✅ Success Criteria

Migration is successful when:
1. ✅ Zero `os.getenv()` calls remain (except in config.py itself)
2. ✅ All tests pass (or same failures as before)
3. ✅ Server starts without errors
4. ✅ Critical API endpoints work
5. ✅ No AttributeError on settings access

---

## 📊 Progress Tracking

| Phase | Files | Calls | Status |
|-------|-------|-------|--------|
| Phase 1 | 3 | 33 | ⏳ Pending |
| Phase 2 | 3 | 13 | ⏳ Pending |
| Phase 3 | 12 | 18 | ⏳ Pending |
| **Total** | **18** | **64** | **0% Complete** |

---

**Ready to start migration with care and attention to detail.**
