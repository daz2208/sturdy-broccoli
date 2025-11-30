# Where Are Seeds Ideas Stored and Visible?

## 📦 Storage Locations

### 1. **Database Storage** (Primary)
**Table:** `build_idea_seeds`  
**Location:** SQLite database at `sturdy-broccoli-main/refactored/syncboard_backend/syncboard.db`

**Schema:**
```sql
CREATE TABLE build_idea_seeds (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,           -- Links to documents table
    knowledge_base_id TEXT,         -- Your KB ID
    title TEXT,                     -- "Build a Real-time Chat App"
    description TEXT,               -- Full description
    difficulty TEXT,                -- beginner/intermediate/advanced
    dependencies TEXT,              -- JSON array of skills needed
    feasibility TEXT,               -- high/medium/low
    effort_estimate TEXT,           -- "2-3 days", "1 week", etc.
    referenced_sections TEXT,       -- JSON array of doc sections
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**How to View Database:**
```bash
# Navigate to backend directory
cd sturdy-broccoli-main/refactored/syncboard_backend

# Query seeds (if sqlite3 installed)
sqlite3 syncboard.db "SELECT id, title, difficulty, feasibility FROM build_idea_seeds LIMIT 10;"

# Or use Python
python3 -c "
from sqlalchemy import create_engine
engine = create_engine('sqlite:///syncboard.db')
result = engine.execute('SELECT COUNT(*) FROM build_idea_seeds')
print(f'Total seeds: {result.fetchone()[0]}')
"
```

---

## 👀 Where You Can SEE Seeds in the UI

### 1. **"What Can I Build" Page** 📍 PRIMARY LOCATION
**URL:** `http://localhost:3000/build`  
**File:** `frontend/src/app/build/page.tsx`

**What You'll See:**
- Quick Ideas tab (instant, from database)
- Full AI Suggestions (uses seeds as context)
- Each idea shows:
  - Title
  - Description
  - Difficulty level
  - Required skills/dependencies
  - Feasibility rating
  - Time estimate
  - "Save Idea" button

**API Called:**
- `GET /quick-ideas` - Fast, database-only retrieval
- `POST /what_can_i_build` - Full suggestions using seeds

---

### 2. **"Saved Ideas" Page** 📍 BOOKMARKED SEEDS
**URL:** `http://localhost:3000/saved-ideas`  
**File:** `frontend/src/app/saved-ideas/page.tsx`

**What You'll See:**
- Ideas you've bookmarked/saved
- Status tracking (saved/in-progress/completed)
- Personal notes
- Progress tracking
- Mega project combinations

**API Called:**
- `GET /saved-ideas` - Your saved/bookmarked ideas

---

## 🔍 How to Access Seeds Right Now

### Option A: Via Frontend UI

1. **Navigate to Build Page:**
   ```
   http://localhost:3000/build
   ```

2. **Click "Quick Ideas" tab** (if there are tabs)
   - Should show instant ideas from database
   - No loading time (cached)

3. **Or click "Get Suggestions" button**
   - Uses seeds to generate full project suggestions

### Option B: Via API (Direct)

**Get Quick Ideas:**
```bash
curl http://localhost:8000/quick-ideas?limit=10 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Get All Idea Seeds:**
```bash
curl http://localhost:8000/idea-seeds?limit=20 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Filter by Difficulty:**
```bash
curl "http://localhost:8000/quick-ideas?difficulty=beginner&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Option C: Via Database (Advanced)

**If you have database access:**
```bash
cd sturdy-broccoli-main/refactored/syncboard_backend

# Check if seeds exist
python3 << EOF
from sqlalchemy import create_engine
engine = create_engine('sqlite:///syncboard.db')

# Count seeds
result = engine.execute('SELECT COUNT(*) FROM build_idea_seeds')
print(f'Total seeds: {result.fetchone()[0]}')

# Show sample
result = engine.execute('SELECT id, title, difficulty FROM build_idea_seeds LIMIT 5')
for row in result:
    print(f"ID {row[0]}: {row[1]} ({row[2]})")
