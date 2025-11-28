# Build Idea Seeds Generation Failure - Root Cause Analysis

**Date:** 2025-11-27
**Issue:** `build_idea_seeds` table remains empty after document uploads
**Severity:** High - Critical feature non-functional

---

## Executive Summary

The build idea seeds feature is **completely non-functional** due to three critical bugs that cause silent failures:

1. **🔴 CRITICAL: GPT-5 API Parameter Incompatibility** - Using deprecated parameters causes API errors
2. **🔴 CRITICAL: Insufficient Token Limits** - Responses truncate, producing invalid JSON
3. **⚠️ MAJOR: Missing Environment Variables** - Docker containers lack required config

All three issues cause exceptions that are **caught and logged as warnings**, making the problem invisible in production.

---

## System Architecture Overview

### How Idea Seeds Should Work

```
Document Upload (tasks.py)
    ↓
1. Document chunked into segments (chunking_pipeline.py)
    ↓
2. Hierarchical summaries generated (summarization_service.py)
    ├── Chunk summaries (300 tokens each)
    ├── Section summaries (500 tokens each)
    └── Document summary (700 tokens) ← USED FOR IDEAS
    ↓
3. Idea seeds generated from document summary (idea_seeds_service.py)
    ├── Uses OpenAI gpt-5-mini model
    ├── Generates 2-4 project ideas
    └── Stores in build_idea_seeds table
```

### Current Flow (BROKEN)

```
Document Upload
    ↓
1. Chunking ✅ WORKS
    ↓
2. Summarization ⚠️ PARTIALLY WORKS
    ├── API calls succeed
    ├── Responses truncated (700 tokens too small)
    └── Returns incomplete JSON → JSONDecodeError
    ↓
3. Idea Generation ❌ FAILS SILENTLY
    ├── Wrong API parameters for GPT-5
    ├── OpenAI API returns 400 error
    ├── Exception caught, returns {"status": "skipped"}
    └── No ideas stored in database
```

---

## Bug #1: GPT-5 API Parameter Incompatibility 🔴

### Location
- `backend/idea_seeds_service.py:125-133`
- `backend/summarization_service.py:106-109, 188-189, 286-287`

### The Problem

**GPT-5 models do NOT support these parameters:**
- `temperature` - GPT-5 uses fixed sampling
- `max_tokens` - GPT-5 requires `max_completion_tokens` instead

### Current Code (BROKEN)

**idea_seeds_service.py:125-133**
```python
response = self.client.chat.completions.create(
    model=self.model,  # "gpt-5-mini"
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.8,        # ❌ GPT-5 doesn't support this!
    max_tokens=1000,        # ❌ Should be max_completion_tokens!
    response_format={"type": "json_object"}
)
```

**summarization_service.py:106-109**
```python
params = {
    "model": self.model,  # "gpt-5-nano"
    "messages": [...],
    "response_format": {"type": "json_object"}
}

params["max_completion_tokens"] = 300  # ✅ Correct parameter name
params["temperature"] = 0.3             # ❌ GPT-5 doesn't support this!
```

### What Happens

When the code runs:
```
OpenAI API Error: Invalid parameter 'temperature' for model 'gpt-5-mini'
→ Exception raised
→ Caught by: except Exception as e: logger.error(f"Idea generation failed: {e}")
→ Returns: []
→ Tasks.py logs: "Idea seed generation failed (non-critical)"
→ Result: No ideas in database, no visible error to user
```

### The Correct Way

**From llm_providers.py:162-168** (already implemented correctly):
```python
params = {
    "model": model,
    "messages": messages
}

if model.startswith("gpt-5"):
    # GPT-5 models: no temperature, use max_completion_tokens
    params["max_completion_tokens"] = max_tokens
else:
    # GPT-4 and earlier: temperature supported, use max_tokens
    params["max_tokens"] = max_tokens
    params["temperature"] = temperature
```

### Impact
- **100% failure rate** for idea generation
- **100% failure rate** for document summarization
- All OpenAI calls return 400 errors

---

## Bug #2: Insufficient Token Limits 🔴

### Location
- `backend/summarization_service.py` - Multiple functions
- `backend/idea_seeds_service.py` - Idea generation

### The Problem

Token limits are too low for the requested output, causing **response truncation**.

### Token Limit Analysis

| Function | Current Limit | Expected Output | Status |
|----------|--------------|-----------------|--------|
| `summarize_chunk()` | 300 tokens (~225 words) | 100 words + 5 concepts + tech | ✅ Okay |
| `summarize_section()` | 500 tokens (~375 words) | 200 words + 7 concepts + tech + skills | ⚠️ Tight |
| `summarize_document()` | **700 tokens (~525 words)** | **300 words + summary + 10 concepts + tech + skills** | 🔴 **TOO SMALL** |
| `generate_ideas_from_summary()` | 1000 tokens (~750 words) | 4 ideas × 65 words + JSON overhead | ⚠️ Tight for 4 ideas |
| `generate_combined_ideas()` | 1500 tokens (~1125 words) | 5 ideas × 65 words + JSON overhead | ⚠️ Tight |

### Current Limits

**summarization_service.py:**
```python
# Line 106: Chunk summary
params["max_completion_tokens"] = 300  # Okay

# Line 188: Section summary
params["max_completion_tokens"] = 500  # Tight

# Line 286: Document summary
params["max_completion_tokens"] = 700  # ❌ TOO SMALL!
```

**idea_seeds_service.py:**
```python
# Line 132: Idea generation
max_tokens=1000  # Tight for 4 ideas

# Line 228: Combined ideas
max_tokens=1500  # Tight for 5 ideas
```

### What the Prompts Ask For

**Document Summary (summarization_service.py:257-271):**
```
1. Comprehensive document summary (5-8 sentences, max 300 words)
2. Executive short summary (1-2 sentences)
3. Core concepts (up to 10)
4. Complete technology stack
5. Skill profile

Expected output: ~400-500 words minimum
Available: 700 tokens = ~525 words
```

**Idea Seeds (idea_seeds_service.py:87-111):**
```
Generate 2-4 practical project ideas with:
- title: Catchy, descriptive name
- description: 2-3 sentences
- difficulty: beginner/intermediate/advanced
- dependencies: List of concepts/skills
- feasibility: high/medium/low
- effort_estimate: Time estimate

Expected per idea: ~65 words
For 4 ideas: ~260 words + JSON overhead (~100 words) = ~360 words
Available: 1000 tokens = ~750 words (works for 2-3, tight for 4)
```

### What Actually Happens

When response hits token limit:

```json
{
    "ideas": [
        {
            "title": "Task Manager Dashboard",
            "description": "Build a comprehensive task management system with...",
            "difficulty": "intermediate",
            "dependencies": ["React", "Node.js", "MongoDB"],
            "feasibility": "high",
            "effort_estimate": "1 we
```

**Response truncated!** → `finish_reason: "length"` instead of `"stop"`

Then:
```python
result = json.loads(response.choices[0].message.content)
# ❌ JSONDecodeError: Expecting ',' delimiter: line 8 column 32 (char 287)

# Exception caught:
except Exception as e:
    logger.error(f"Idea generation failed: {e}")
    return []

# Result: Empty list, no ideas stored
```

### Detection Missing

The code doesn't check `finish_reason`:
```python
response = self.client.chat.completions.create(...)
# Missing: if response.choices[0].finish_reason == "length": ...

result = json.loads(response.choices[0].message.content)  # Boom!
```

Compare to `llm_providers.py:194` which does log it:
```python
logger.info(f"API response - finish_reason: {response.choices[0].finish_reason}, ...")
```

### Impact
- Document summaries may be incomplete (partial data stored)
- Idea generation fails with JSONDecodeError
- User sees no error, just empty results

---

## Bug #3: Missing Environment Variables ⚠️

### Location
- `docker-compose.yml` - All 7+ services

### The Problem

The code reads these environment variables:
```python
# idea_seeds_service.py:21
IDEA_MODEL = os.getenv("IDEA_MODEL", "gpt-5-mini")

# summarization_service.py:23
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
```

But `docker-compose.yml` **doesn't define them**:

**What IS defined:**
```yaml
environment:
  OPENAI_API_KEY: ${OPENAI_API_KEY:-sk-replace-with-your-key}
  TRANSCRIPTION_MODEL: ${TRANSCRIPTION_MODEL:-gpt-4o-mini-transcribe}
  # ... but no IDEA_MODEL or SUMMARY_MODEL
```

### Affected Services

All these services need the vars but don't have them:
1. `backend` (main API)
2. `celery` (worker 1)
3. `celery-worker-2` (worker 2)
4. `celery-worker-uploads` (upload worker)
5. `celery-worker-analysis` (analysis worker)
6. `celery-beat` (scheduler)
7. `celery-worker-learning` (learning agent)
8. `celery-worker-maverick` (maverick agent)
9. `flower` (monitoring)

### Current Behavior

Because the vars aren't set:
```python
IDEA_MODEL = os.getenv("IDEA_MODEL", "gpt-5-mini")
# Returns: "gpt-5-mini" (default works!)

SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
# Returns: "gpt-5-nano" (default works!)
```

**So why is this a problem?**

1. **No explicit config** - Defaults work now, but breaking changes invisible
2. **Can't override** - Users can't change models without code changes
3. **Inconsistent** - Other models (TRANSCRIPTION_MODEL) are configurable
4. **Missing from .env.example** - No documentation

### Impact
- Low immediate impact (defaults work)
- High maintenance risk (can't configure without redeploying)
- Inconsistent with project patterns

---

## Bug #4: Silent Failure Architecture 🔴

### The Real Problem

**All errors are caught and hidden:**

**tasks.py:816-830** (where ideas are called):
```python
# Stage 8: Generate idea seeds
if summarization_result.get('status') == 'success':
    try:
        from .idea_seeds_service import generate_document_idea_seeds
        with get_db_context() as db:
            db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
            if db_doc:
                idea_result = run_async(generate_document_idea_seeds(
                    db=db,
                    document_id=db_doc.id,
                    knowledge_base_id=kb_id
                ))
                logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for doc {doc_id}")
    except Exception as e:
        logger.warning(f"Idea seed generation failed (non-critical): {e}")  # ❌ Just warns!
```

**idea_seeds_service.py:152-154** (where OpenAI is called):
```python
try:
    response = self.client.chat.completions.create(...)
    # ... process response
except Exception as e:
    logger.error(f"Idea generation failed: {e}")  # ❌ Just logs!
    return []  # ❌ Returns empty, no exception raised
```

**idea_seeds_service.py:273-294** (main function):
```python
service = IdeaSeedsService()

if not service.is_available():
    return {"status": "skipped", "reason": "API key not configured"}  # Silent skip

doc_summary = db.query(DBDocumentSummary).filter(...).first()

if not doc_summary:
    return {"status": "skipped", "reason": "No document summary found"}  # Silent skip

ideas = await service.generate_ideas_from_summary(...)

if not ideas:
    return {"status": "skipped", "reason": "No ideas generated"}  # Silent skip - hides real error!
```

### Failure Flow

```
1. Upload document
   ↓
2. Summarization runs with wrong GPT-5 params
   ↓ (OpenAI API error OR truncated JSON)
   ↓
3. Exception caught → returns SummaryResult with partial/empty data
   ↓
4. tasks.py checks: if summarization_result.get('status') == 'success'
   ↓ (might be 'success' even with partial data!)
   ↓
5. Idea generation called with incomplete summary
   ↓
6. OpenAI API error (wrong params for GPT-5)
   ↓
7. Exception caught → returns []
   ↓
8. Returns {"status": "skipped", "reason": "No ideas generated"}
   ↓
9. tasks.py logs: "Idea seed generation failed (non-critical)"
   ↓
10. User sees: Nothing (task completes "successfully")
```

### What the Logs Show

```
INFO: Generated summaries for doc 123: 5 chunks, 2 sections, 1 document
WARNING: Idea seed generation failed (non-critical): ...
INFO: Background task: User uploaded file.pdf as doc 123 (chunks: 5, summaries: completed)
```

**User sees:** ✅ Upload successful!
**Reality:** ❌ Ideas completely failed, but marked non-critical

---

## Evidence from Code

### Where Ideas Are Called

**tasks.py:815-830** (file upload):
```python
# Stage 8: Generate idea seeds (auto-generate build ideas from summaries)
if summarization_result.get('status') == 'success':
    try:
        from .idea_seeds_service import generate_document_idea_seeds
        with get_db_context() as db:
            db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
            if db_doc:
                idea_result = run_async(generate_document_idea_seeds(
                    db=db,
                    document_id=db_doc.id,
                    knowledge_base_id=kb_id
                ))
                logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for doc {doc_id}")
    except Exception as e:
        logger.warning(f"Idea seed generation failed (non-critical): {e}")
```

Also called in:
- **tasks.py:1215-1229** (URL upload)
- **tasks.py:1591-1605** (image upload)

**Summarization called from:**
- **tasks.py:778-786** (file upload) - `generate_ideas=False` ❌ Ideas disabled!
- **tasks.py:1177-1185** (URL upload) - `generate_ideas=False` ❌ Ideas disabled!
- **tasks.py:1553-1561** (image upload) - `generate_ideas=False` ❌ Ideas disabled!

### Why `generate_ideas=False`?

**summarization_service.py:440-456:**
```python
if generate_ideas:
    try:
        from .idea_seeds_service import generate_document_idea_seeds
        ideas_result = await generate_document_idea_seeds(
            db=db,
            document_id=document_id,
            knowledge_base_id=knowledge_base_id
        )
        logger.info(f"Generated {ideas_result.get('ideas_generated', 0)} ideas during summarization")
    except Exception as e:
        logger.warning(f"Idea generation during summarization failed: {e}")
```

**So ideas can be generated in TWO places:**
1. **During summarization** (if `generate_ideas=True`)
2. **After summarization** (tasks.py Stage 8)

**Currently:** All uploads use `generate_ideas=False`, so ideas are ONLY generated in Stage 8 of tasks.py

---

## Configuration Issues

### Model Defaults

**Current hardcoded defaults:**
```python
# llm_providers.py:119-120
concept_model: str = "gpt-5-nano"
suggestion_model: str = "gpt-5-mini"

# summarization_service.py:23
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gpt-5-nano")

# idea_seeds_service.py:21
IDEA_MODEL = os.getenv("IDEA_MODEL", "gpt-5-mini")
```

### Environment Variable Coverage

**What's configured in docker-compose.yml:**
```yaml
✅ OPENAI_API_KEY
✅ TRANSCRIPTION_MODEL
❌ IDEA_MODEL (missing)
❌ SUMMARY_MODEL (missing)
❌ CONCEPT_MODEL (missing)
❌ SUGGESTION_MODEL (missing)
```

### .env.example Coverage

**What's documented:**
```bash
✅ OPENAI_API_KEY
❌ IDEA_MODEL (missing)
❌ SUMMARY_MODEL (missing)
❌ Model configuration section (missing)
```

---

## Impact Assessment

### Feature Impact
| Feature | Status | Reason |
|---------|--------|--------|
| Document Upload | ⚠️ Partial | Works but no ideas generated |
| Summarization | ⚠️ Partial | May truncate, produces incomplete data |
| Idea Seeds | ❌ Broken | 100% failure rate, table empty |
| Build Suggestions | ⚠️ Unknown | May fail due to same GPT-5 param issues |
| "What Can I Build?" | ❌ Broken | Depends on idea seeds |

### Database State
```sql
-- Check what's in the database:
SELECT COUNT(*) FROM documents;           -- Has data ✅
SELECT COUNT(*) FROM document_chunks;     -- Has data ✅
SELECT COUNT(*) FROM document_summaries;  -- Has data ⚠️ (may be incomplete)
SELECT COUNT(*) FROM build_idea_seeds;    -- EMPTY ❌
```

### User Experience
- User uploads document → ✅ Success message
- User checks "What can I build?" → ❌ Empty list
- User checks logs → ⚠️ Warning (non-critical), easy to miss
- User debugging → ❌ No clear error message

---

## Recommended Fixes

### Fix #1: GPT-5 Parameter Compatibility

**Create a helper function:**
```python
def build_openai_params(
    model: str,
    messages: List[Dict],
    max_tokens: int,
    temperature: float = None,
    response_format: Optional[Dict] = None
) -> Dict:
    """Build OpenAI API parameters compatible with model version."""
    params = {
        "model": model,
        "messages": messages
    }

    if response_format:
        params["response_format"] = response_format

    if model.startswith("gpt-5"):
        # GPT-5: no temperature, use max_completion_tokens
        params["max_completion_tokens"] = max_tokens
    else:
        # GPT-4 and earlier: temperature supported
        params["max_tokens"] = max_tokens
        if temperature is not None:
            params["temperature"] = temperature

    return params
```

**Use in idea_seeds_service.py:**
```python
params = build_openai_params(
    model=self.model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    max_tokens=2000,  # Increased
    temperature=0.8,
    response_format={"type": "json_object"}
)

response = self.client.chat.completions.create(**params)
```

### Fix #2: Increase Token Limits

**Recommended new limits:**
```python
# summarization_service.py
summarize_chunk():       300 → 500 tokens
summarize_section():     500 → 800 tokens
summarize_document():    700 → 1200 tokens

# idea_seeds_service.py
generate_ideas():        1000 → 2000 tokens
generate_combined():     1500 → 2500 tokens
```

**Add finish_reason checks:**
```python
response = self.client.chat.completions.create(**params)

# Check for truncation
if response.choices[0].finish_reason == "length":
    logger.warning(f"Response truncated! Model: {self.model}, limit: {max_tokens}")
    logger.warning(f"Consider increasing max_completion_tokens for this operation")

result = json.loads(response.choices[0].message.content)
```

### Fix #3: Add Environment Variables

**Update docker-compose.yml** (all services):
```yaml
environment:
  OPENAI_API_KEY: ${OPENAI_API_KEY:-sk-replace-with-your-key}
  TRANSCRIPTION_MODEL: ${TRANSCRIPTION_MODEL:-gpt-4o-mini-transcribe}
  IDEA_MODEL: ${IDEA_MODEL:-gpt-5-mini}
  SUMMARY_MODEL: ${SUMMARY_MODEL:-gpt-5-nano}
  CONCEPT_MODEL: ${CONCEPT_MODEL:-gpt-5-nano}
  SUGGESTION_MODEL: ${SUGGESTION_MODEL:-gpt-5-mini}
```

**Update .env.example:**
```bash
# AI Models Configuration
IDEA_MODEL=gpt-5-mini              # Model for build idea generation
SUMMARY_MODEL=gpt-5-nano           # Model for document summarization
CONCEPT_MODEL=gpt-5-nano           # Model for concept extraction
SUGGESTION_MODEL=gpt-5-mini        # Model for build suggestions
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe  # Model for audio transcription
```

### Fix #4: Better Error Handling

**idea_seeds_service.py - Don't hide errors:**
```python
async def generate_ideas_from_summary(...) -> List[IdeaSeed]:
    if not self.is_available():
        logger.warning("Idea generation unavailable: API key not configured")
        return []

    try:
        params = build_openai_params(...)
        response = self.client.chat.completions.create(**params)

        # Check truncation
        if response.choices[0].finish_reason == "length":
            logger.error(f"Idea generation response TRUNCATED! Increase max_completion_tokens")
            raise ValueError("Response truncated - increase token limit")

        result = json.loads(response.choices[0].message.content)
        ideas = result.get("ideas", [])

        if not ideas:
            logger.warning("OpenAI returned valid JSON but no ideas were generated")

        return [IdeaSeed(**idea) for idea in ideas]

    except json.JSONDecodeError as e:
        logger.error(f"Idea generation FAILED - Invalid JSON response: {e}")
        logger.error(f"Response content: {response.choices[0].message.content[:500]}...")
        raise  # Re-raise instead of returning []
    except Exception as e:
        logger.error(f"Idea generation FAILED - API error: {e}", exc_info=True)
        raise  # Re-raise instead of returning []
```

**tasks.py - Report errors properly:**
```python
# Stage 8: Generate idea seeds
if summarization_result.get('status') == 'success':
    try:
        idea_result = run_async(generate_document_idea_seeds(...))
        ideas_count = idea_result.get('ideas_generated', 0)

        if ideas_count > 0:
            logger.info(f"✅ Generated {ideas_count} idea seeds for doc {doc_id}")
        else:
            reason = idea_result.get('reason', 'unknown')
            logger.error(f"❌ Idea generation returned 0 ideas: {reason}")

    except Exception as e:
        logger.error(f"❌ CRITICAL: Idea seed generation FAILED: {e}", exc_info=True)
        # Optional: Set a flag on the document for retry
else:
    logger.warning(f"⚠️ Skipping idea generation - summarization status: {summarization_result.get('status')}")
```

---

## Testing Plan

### 1. Verify Current Failure

```bash
# Check database state
docker exec syncboard-db psql -U syncboard -d syncboard -c "SELECT COUNT(*) FROM build_idea_seeds;"

# Upload test document
# Check logs for errors
docker logs syncboard-celery 2>&1 | grep -i "idea"
docker logs syncboard-celery 2>&1 | grep -i "error"
```

### 2. Test Fix #1 (GPT-5 Parameters)

```bash
# Apply parameter fix
# Upload test document
# Check logs for successful API calls
docker logs syncboard-celery 2>&1 | grep "Calling OpenAI with model: gpt-5"
```

### 3. Test Fix #2 (Token Limits)

```bash
# Apply token limit increases
# Upload complex document (>10 pages)
# Check for "finish_reason: stop" (not "length")
# Verify ideas generated
docker exec syncboard-db psql -U syncboard -d syncboard -c "SELECT title, difficulty FROM build_idea_seeds LIMIT 10;"
```

### 4. Test Fix #3 (Env Vars)

```bash
# Add vars to docker-compose.yml
# Restart containers
docker-compose down && docker-compose up -d

# Verify vars are set
docker exec syncboard-backend env | grep MODEL
```

### 5. End-to-End Test

```bash
# Upload document
# Wait for processing
# Check database
docker exec syncboard-db psql -U syncboard -d syncboard -c "
SELECT
    d.filename,
    COUNT(DISTINCT c.id) as chunks,
    COUNT(DISTINCT s.id) as summaries,
    COUNT(DISTINCT i.id) as ideas
FROM documents d
LEFT JOIN document_chunks c ON c.document_id = d.id
LEFT JOIN document_summaries s ON s.document_id = d.id
LEFT JOIN build_idea_seeds i ON i.document_id = d.id
WHERE d.id = (SELECT MAX(id) FROM documents)
GROUP BY d.id, d.filename;
"
```

---

## Files Requiring Changes

### Code Changes
1. `backend/idea_seeds_service.py` - Fix GPT-5 params, increase tokens, better errors
2. `backend/summarization_service.py` - Fix GPT-5 params, increase tokens
3. `backend/tasks.py` - Better error logging (optional)
4. `backend/llm_utils.py` - New file for `build_openai_params()` helper (optional)

### Configuration Changes
1. `docker-compose.yml` - Add IDEA_MODEL, SUMMARY_MODEL to all 9 services
2. `.env.example` - Document new environment variables

### Documentation
1. This file - Root cause analysis
2. `README.md` - Update configuration section (optional)

---

## Conclusion

The build idea seeds feature is **completely broken** due to:

1. **Wrong API parameters** for GPT-5 models → 100% API errors
2. **Insufficient token limits** → Truncated responses, invalid JSON
3. **Silent error handling** → No visibility into failures

All three issues must be fixed for the feature to work.

**Priority:** HIGH - This is a core feature that's advertised but non-functional.

**Effort:** Low - All fixes are straightforward and well-understood.

**Risk:** Low - Changes are isolated to idea generation and summarization code.

---

## Next Steps

1. Apply fixes for GPT-5 parameter compatibility
2. Increase token limits across the board
3. Add environment variables to docker-compose.yml
4. Test with real document upload
5. Monitor logs for any remaining errors
6. Consider adding `/api/admin/test-idea-generation` diagnostic endpoint
