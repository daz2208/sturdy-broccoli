# SyncBoard Issues Diagnosis and Fixes

**Date:** 2025-11-30  
**Reported Issues:**
1. On page refresh, user gets kicked back to login page
2. Agents (Maverick and others) not showing output
3. Seeds functionality not working/outputting

---

## Issue 1: Authentication Lost on Page Refresh

### Root Cause Analysis

**What's Happening:**
- Token IS stored in localStorage (`api.ts:44`)
- Token IS loaded when API client initializes (`api.ts:42-45`)
- Zustand persist middleware IS configured (`auth.ts:68-70`)
- However, the auth state may not be properly rehydrated on page load

**The Problem:**
1. When page refreshes, Next.js re-renders from server
2. localStorage isn't available during SSR
3. The API client loads token in constructor, but zustand state may not sync immediately
4. Components check `isAuthenticated` from zustand before it's rehydrated
5. User gets redirected to /login even though token exists

**File:** `frontend/src/stores/auth.ts`
**Issue:** The `checkAuth()` function only checks if token exists, doesn't validate it with backend

```typescript
checkAuth: () => {
  const isAuth = api.isAuthenticated();  // Only checks if token exists locally
  set({ isAuthenticated: isAuth });
},
```

### Fix Strategy

**Option 1: Add useEffect to root layout** ✓ RECOMMENDED
Add auth check on app initialization in root layout:

```typescript
// In app/layout.tsx
useEffect(() => {
  const { checkAuth } = useAuthStore.getState();
  checkAuth();
}, []);
```

**Option 2: Improve checkAuth function**
Make checkAuth validate token with backend:

```typescript
checkAuth: async () => {
  const isAuth = api.isAuthenticated();
  if (isAuth) {
    try {
      // Validate token with backend
      await api.getHealth(); // or any authenticated endpoint
      set({ isAuthenticated: true });
    } catch {
      // Token invalid
      api.clearToken();
      set({ isAuthenticated: false });
    }
  } else {
    set({ isAuthenticated: false });
  }
},
```

**Option 3: Use middleware to sync zustand with localStorage**
Already implemented via persist middleware, but ensure it runs before components mount.

---

## Issue 2: Agents Not Showing Output

### Root Cause Analysis

**What's Happening:**
- Frontend correctly calls `/learning/agents/overview` (`agents/page.tsx:258`)
- Backend endpoint exists (`backend/routers/learning.py:720`)
- Endpoint calls `get_agent_status()` and `get_maverick_status()`

**The Problem:**
The agents (Learning Agent & Maverick) are singleton instances that return their current state. If they haven't been initialized or run any tasks, they return default/empty values:

```python
# backend/learning_agent.py and maverick_agent.py
# These are likely returning default values:
{
  "status": "idle",
  "mode": "observing",
  "total_observations": 0,
  "total_actions": 0,
  "autonomous_rules_created": 0,
  ...
}
```

**Verification:**
Check if agents are actually initialized and running:
- Agents should be background tasks/workers
- They should have scheduled jobs (cron/celery)
- They need to observe user activity and make decisions

**Files to Check:**
- `backend/learning_agent.py` - Check if agent is running
- `backend/maverick_agent.py` - Check if maverick is active
- `backend/tasks.py` - Check if background tasks are scheduled
- `backend/main.py` - Check if agents start on app startup

### Fix Strategy

1. **Verify agents are initialized on startup**
   - Check `main.py` for agent initialization
   - Ensure background tasks are scheduled

2. **Manually trigger agent tasks to generate initial data**
   - Use the "Trigger Tasks" buttons on the agents page
   - OR run background tasks manually via backend

3. **Ensure database tables exist**
   - Agents store data in DB (learned rules, hypotheses, etc.)
   - Run Alembic migrations if needed

---

## Issue 3: Seeds Not Working/Outputting

### Root Cause Analysis

**What's Happening:**
- Seeds API endpoints exist (`backend/routers/build_suggestions.py`)
- IdeaSeedsService exists (`backend/idea_seeds_service.py`)
- Frontend calls correct endpoints

**Possible Problems:**
1. **No documents with summaries** - Seeds are generated from document summaries
2. **OpenAI API key not configured** - Service requires OpenAI for generation
3. **Seeds never generated** - Need to run backfill or generate on document upload
4. **Database empty** - No idea_seeds table data

**Files:**
- `backend/idea_seeds_service.py:58-60` - Checks if OpenAI API key exists
- `backend/routers/build_suggestions.py` - Has `/idea-seeds` endpoints
- `backend/routers/build_suggestions.py` - Has `/idea-seeds/backfill` endpoint

### Fix Strategy

1. **Check OpenAI API key is configured**
   ```bash
   # In backend/.env
   OPENAI_API_KEY=sk-...
   ```

2. **Check if documents have summaries**
   - Seeds are generated from document summaries
   - Need documents uploaded and summarized first

3. **Run backfill to generate seeds**
   ```bash
   POST /idea-seeds/backfill
   ```
   This will process existing documents and generate idea seeds

4. **Verify database table exists**
   ```sql
   SELECT * FROM idea_seeds LIMIT 10;
   ```

---

## Quick Diagnostic Commands

### Check Auth Token in Browser Console
```javascript
// Open browser console on frontend
localStorage.getItem('token')
localStorage.getItem('auth-storage')
```

### Check Agents Status via API
```bash
# Get auth token first, then:
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/learning/agents/overview
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/learning/maverick/hypotheses
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/learning/rules
```

### Check Seeds via API
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/idea-seeds?limit=10
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/quick-ideas?limit=10
```

### Check Database
```bash
# In backend directory
python -c "
from database import SessionLocal
from db_models import DBLearnedRule, DBIdeaSeed
db = SessionLocal()
print('Learned Rules:', db.query(DBLearnedRule).count())
print('Idea Seeds:', db.query(DBIdeaSeed).count())
"
```

---

## Implementation Priority

### HIGH PRIORITY (User-Blocking)
1. **Fix auth persistence** - Users can't use app after refresh
   - Implement Option 1 (useEffect in layout) 
   - Time: 5 minutes

### MEDIUM PRIORITY (Feature Not Working)
2. **Initialize agents and generate initial data**
   - Manually trigger agent tasks
   - Verify background workers are running
   - Time: 15-30 minutes

3. **Verify and backfill idea seeds**
   - Check OpenAI key
   - Run backfill endpoint
   - Time: 10-15 minutes

### LOW PRIORITY (Enhancement)
4. **Add better error messages**
   - Show why agents have no data
   - Show why seeds are empty
   - Time: 20 minutes

---

## Testing Checklist

After fixes:
- [ ] Refresh page - should stay logged in
- [ ] Check localStorage - token should persist
- [ ] Visit /agents - should see agent stats (not all zeros)
- [ ] Trigger agent tasks - should show activity
- [ ] Visit saved ideas - should see quick ideas/seeds
- [ ] Check browser console - no 401 errors

