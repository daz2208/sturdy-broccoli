# Seed Generation Restoration - Rollback Instructions

**Date:** December 4, 2025
**Change:** Restored seed generation during document upload (Stage 8)
**Reason:** Enable Quick Ideas endpoint to show pre-computed build ideas

---

## What Was Changed

### Files Modified:
1. `backend/idea_seeds_service.py` - **RESTORED** (was deleted in commit 5f64aaa)
2. `backend/tasks.py` - Re-enabled Stage 8 seed generation calls (3 locations)
3. `backend/config.py` - Added IDEA_MODEL configuration (if needed)

### What Seeds Do:
- Generated during document upload (after summarization succeeds)
- Cost: ~$0.01 per document (2-4 ideas, 2000 tokens)
- Stored in `build_idea_seeds` table
- Used ONLY by `/quick-ideas` endpoint (free, instant browsing)
- NOT used by `/what_can_i_build` (that stays pure KB synthesis)

---

## Quick Rollback (If Something Breaks)

### Option 1: Git Revert (Recommended)

```bash
# Find the commit hash
git log --oneline | head -5

# Revert the seed restoration commit
git revert <commit-hash>
git push origin claude/fix-windows-compatibility-014QorggTv6RvNhsJsqjQVfH
```

### Option 2: Manual Rollback

```bash
# 1. Delete the restored service
rm backend/idea_seeds_service.py

# 2. Remove Stage 8 calls from tasks.py
# Edit backend/tasks.py and remove the 3 "Stage 8" blocks

# 3. Restart services
docker-compose restart backend celery celery-worker-2
```

---

## Verification After Rollback

### Check Seeds Are NOT Being Generated:

```bash
# Upload a test document
# Then check the table
docker exec syncboard-db psql -U syncboard -d syncboard -c \
  "SELECT COUNT(*) FROM build_idea_seeds WHERE created_at > NOW() - INTERVAL '5 minutes';"

# Should return: 0 (no new seeds)
```

### Check Quick Ideas Returns Empty:

```bash
curl http://localhost:3000/api/v1/quick-ideas

# Should return: {"count": 0, "ideas": [], "message": "No pre-computed ideas yet..."}
```

### Check What Can I Build Still Works:

```bash
curl -X POST http://localhost:3000/api/v1/what_can_i_build \
  -H "Content-Type: application/json" \
  -d '{"max_suggestions": 3}'

# Should return: Build suggestions (not affected by rollback)
```

---

## What to Check If Things Break

### Symptom: Seeds Not Being Generated

**Check logs:**
```bash
docker logs syncboard-celery 2>&1 | grep -i "idea seed"
docker logs syncboard-celery 2>&1 | grep -i "error"
```

**Check database:**
```sql
-- Check if table exists
SELECT COUNT(*) FROM build_idea_seeds;

-- Check recent uploads
SELECT filename, created_at FROM documents ORDER BY created_at DESC LIMIT 5;

-- Check if summaries were created
SELECT COUNT(*) FROM document_summaries WHERE created_at > NOW() - INTERVAL '1 hour';
```

**Common issues:**
- GPT-5 API errors (temperature parameter)
- Token limit truncation (response incomplete)
- Missing IDEA_MODEL env var
- Summarization failed (Stage 7), so Stage 8 skipped

---

### Symptom: Quick Ideas Returns Nothing

**Expected if:**
- No documents uploaded yet
- Rollback was performed (seeds deleted)
- Seed generation is failing silently

**Check:**
```sql
SELECT COUNT(*) FROM build_idea_seeds;
-- Should be > 0 if seeds were generated

SELECT title, difficulty, created_at
FROM build_idea_seeds
ORDER BY created_at DESC
LIMIT 5;
```

---

### Symptom: What Can I Build Broken

**This should NOT happen** - What Can I Build doesn't use seeds.

**If it breaks anyway:**
```bash
# Check if build_suggester was accidentally modified
git diff backend/build_suggester.py

# Check for seed references that shouldn't exist
grep -r "idea_seed" backend/build_suggester.py
grep -r "idea_seed" backend/llm_providers.py

# Should return: NO MATCHES
```

**If seeds accidentally got into What Can I Build, rollback immediately.**

---

## Safe Restoration (If Rollback Needed)

To restore seeds again after fixing issues:

```bash
# 1. Fix the bug first (check SEED_GENERATION_FAILURE_ANALYSIS.md)

# 2. Cherry-pick the seed restoration commit
git cherry-pick <original-seed-commit>

# 3. Test with one document before enabling for all
```

---

## Emergency Kill Switch

If seeds are causing problems and you need to stop them NOW without code changes:

### Option 1: Environment Variable

```bash
# Add to .env
ENABLE_IDEA_SEEDS=false

# Restart
docker-compose restart
```

### Option 2: Database Flag

```sql
-- Disable for specific user
UPDATE users SET enable_seed_generation = false WHERE username = 'problematic_user';
```

### Option 3: Comment Out Stage 8

```python
# In backend/tasks.py, comment out Stage 8:
# if summarization_result.get('status') == 'success':
#     # Stage 8 code here...
```

---

## Rollback Decision Tree

```
Are seeds being generated?
├─ NO → Check logs, check summarization, check API errors
│        If can't fix → ROLLBACK
│
└─ YES → Are they showing in Quick Ideas?
         ├─ NO → Check table, check query, check KB ID
         │        If can't fix → ROLLBACK
         │
         └─ YES → Is What Can I Build still working?
                  ├─ NO → ROLLBACK IMMEDIATELY (seeds contaminated it)
                  └─ YES → Success! Keep it.
```

---

## Contact/Debug

If you need to rollback and don't know why:

1. **Capture logs first:**
```bash
docker logs syncboard-celery > celery_error.log 2>&1
docker logs syncboard-backend > backend_error.log 2>&1
```

2. **Check database state:**
```bash
docker exec syncboard-db pg_dump -U syncboard syncboard --schema-only > schema_backup.sql
```

3. **Perform rollback** (Option 1 or 2 above)

4. **Document what broke** in `SEED_GENERATION_ISSUES.md` for next attempt

---

## Success Criteria (Seeds Working)

✅ Upload document → logs show "Generated X idea seeds for doc Y"
✅ Quick Ideas endpoint returns seeds
✅ Seeds in database: `SELECT COUNT(*) FROM build_idea_seeds;` > 0
✅ What Can I Build still works (not using seeds)
✅ No GPT-5 API errors in logs
✅ Cost per upload: ~$0.01 (reasonable)

---

*Created: December 4, 2025*
*Purpose: Safe restoration of seed generation with clear rollback path*
