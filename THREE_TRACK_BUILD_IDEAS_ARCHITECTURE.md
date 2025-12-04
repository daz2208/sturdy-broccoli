# Three-Track Build Ideas Architecture

## 🎯 The Problem

**Original Design:**
- Single `/what_can_i_build` endpoint trying to serve two different needs
- Seeds generated during ingestion (Stage 8) but unclear how to use them
- Tension between "fast exploration" vs "deep KB analysis"

**The Core Conflict:**
```
Fast + Cheap (seeds only) ←→ Slow + Expensive (full KB query)
```

One endpoint can't optimize for both without compromising one use case.

---

## ✅ Proposed Solution: Three-Track System

Instead of forcing users to choose between seeds or KB, provide **three complementary approaches** that work together:

### **Track 1: Quick Ideas (Pre-Generated Seeds)**

**Endpoint:** `GET /quick-ideas`

**How It Works:**
- Returns pre-generated seeds from `build_idea_seeds` table
- Seeds already created during document ingestion (Stage 8)
- Simple database query, no AI calls
- Can filter by difficulty, document, or tags

**Performance:**
- Speed: Instant (<100ms)
- Cost: $0 (no AI call)
- Quality: Good (focused on single document context)

**Use Cases:**
- "Show me quick ideas from my latest uploads"
- "What can I build with THIS specific document?"
- "Give me 10 project ideas to browse"

**UI/UX:**
```
┌─────────────────────────────────────┐
│  Quick Ideas (12 available)         │
├─────────────────────────────────────┤
│  💡 API Gateway for n8n Workflows   │
│     Difficulty: Intermediate        │
│     [Expand This →]                 │
├─────────────────────────────────────┤
│  💡 Video Pipeline Automation       │
│     Difficulty: Advanced            │
│     [Expand This →]                 │
└─────────────────────────────────────┘
```

---

### **Track 2: What Can I Build (Full KB Synthesis)**

**Endpoint:** `POST /what_can_i_build`

**How It Works:**
- Queries concepts from `document_summaries.key_concepts` across ALL documents
- AI synthesizes ideas using entire knowledge base
- Cross-references multiple docs to suggest complex builds
- Returns 3-5 comprehensive, detailed build plans

**Performance:**
- Speed: 20-30 seconds
- Cost: $0.20-0.50 per generation
- Quality: Excellent (contextual, comprehensive)

**Use Cases:**
- "What are the most valuable things I can build with ALL my knowledge?"
- "Generate builds that combine multiple areas of my expertise"
- "Deep analysis of build opportunities"

**UI/UX:**
```
┌─────────────────────────────────────┐
│  🔬 Analyzing 131 concepts from     │
│     40 documents...                 │
│                                     │
│  ⏳ Generating comprehensive plans  │
│     (this takes 20-30 seconds)      │
└─────────────────────────────────────┘

↓

┌─────────────────────────────────────┐
│  Generated 4 Build Plans:           │
│                                     │
│  1. AI-Powered SEO Platform         │
│     • n8n + BigQuery + FastAPI      │
│     • 40-80 hours                   │
│     [View Full Plan →]              │
│                                     │
│  2. Data-to-Video Pipeline          │
│     • Django + Celery + PyTorch     │
│     • 80-140 hours                  │
│     [View Full Plan →]              │
└─────────────────────────────────────┘
```

---

### **Track 3: Expand Seed (Hybrid Approach)** ⭐ **NEW**

**Endpoint:** `POST /expand-seed/{seed_id}`

**How It Works:**
- Takes ONE seed idea as starting point
- Queries related concepts from KB using similarity/tags
- AI expands seed into full build plan with KB context
- Returns detailed plan focused on that specific idea

**Performance:**
- Speed: 8-15 seconds
- Cost: $0.05-0.10 per expansion
- Quality: Very Good (focused but contextual)

**Use Cases:**
- "I like THIS seed idea, give me the full plan"
- "Expand this concept with my related knowledge"
- "Middle ground between quick and comprehensive"

**UI/UX:**
```
Quick Idea Card:
┌─────────────────────────────────────┐
│  💡 Value Alignment Service         │
│     Difficulty: Intermediate        │
│     Source: salvage/value_align.py  │
│                                     │
│     [Expand This →]                 │
└─────────────────────────────────────┘

↓ (User clicks "Expand This")

┌─────────────────────────────────────┐
│  🔬 Expanding with related KB...    │
│     • FastAPI patterns              │
│     • SQLModel repositories         │
│     • n8n integration docs          │
│                                     │
│  ⏳ Generating full build plan      │
│     (this takes 10-15 seconds)      │
└─────────────────────────────────────┘

↓

[Full detailed build plan displayed]
```

---

## 🔧 Implementation Details

### **1. Seed Generation (Stage 8 - Keep As-Is)**

```python
# During document ingestion (after summarization success)
async def generate_seeds(doc_id: int, summary: dict):
    """
    Generate 2-4 simple seed ideas per document
    Cost: ~$0.005-0.01 per document
    """
    prompt = f"""
    Based on this document summary:
    {summary}
    
    Generate 2-4 project seed ideas in JSON:
    [
      {{
        "title": "...",
        "description": "1-2 sentences",
        "difficulty": "beginner|intermediate|advanced",
        "key_technologies": ["..."],
        "effort_estimate": "X-Y hours"
      }}
    ]
    """
    
    seeds = await call_gpt_5_mini(prompt, max_tokens=5000)
    
    for seed in seeds:
        db.add(BuildIdeaSeed(
            document_id=doc_id,
            title=seed['title'],
            description=seed['description'],
            difficulty=seed['difficulty'],
            # ... other fields
        ))
```

**Keep generating seeds because they're useful for ALL three tracks!**

---

### **2. Quick Ideas Endpoint**

```python
@router.get('/quick-ideas')
def get_quick_ideas(
    limit: int = 12,
    difficulty: Optional[str] = None,
    document_id: Optional[int] = None
):
    """
    Returns pre-generated seeds - no AI call needed
    """
    query = db.query(BuildIdeaSeed)
    
    if difficulty:
        query = query.filter(BuildIdeaSeed.difficulty == difficulty)
    
    if document_id:
        query = query.filter(BuildIdeaSeed.document_id == document_id)
    
    seeds = query.order_by(BuildIdeaSeed.created_at.desc()).limit(limit).all()
    
    return {
        'count': len(seeds),
        'ideas': [format_seed(s) for s in seeds]
    }
```

---

### **3. What Can I Build (Current Implementation)**

```python
@router.post('/what_can_i_build')
async def generate_build_ideas(kb_id: str):
    """
    Full KB synthesis - queries all concepts and generates comprehensive plans
    """
    # Get all concepts from document_summaries (via fallback)
    concepts = get_all_concepts(kb_id)
    
    # Get tech stack, skill profiles
    tech_stack = get_tech_stack(kb_id)
    
    prompt = f"""
    Based on this knowledge base:
    - {len(concepts)} concepts across multiple documents
    - Tech stack: {tech_stack}
    
    Generate 3-5 comprehensive build ideas that:
    1. Combine concepts from multiple documents
    2. Are realistic and achievable
    3. Have clear value propositions
    ...
    """
    
    ideas = await call_gpt_5(prompt, max_tokens=20000)
    return ideas
```

---

### **4. Expand Seed (NEW)**

```python
@router.post('/expand-seed/{seed_id}')
async def expand_seed(seed_id: int):
    """
    Takes a seed and expands it with full KB context
    """
    seed = db.query(BuildIdeaSeed).get(seed_id)
    if not seed:
        raise HTTPException(404)
    
    # Get related concepts from KB
    related_concepts = find_related_concepts(
        seed.key_technologies,
        seed.title
    )
    
    # Get the source document summary
    doc_summary = get_document_summary(seed.document_id)
    
    prompt = f"""
    Expand this project seed into a full build plan:
    
    SEED:
    {seed.title}
    {seed.description}
    Difficulty: {seed.difficulty}
    
    RELATED KB CONTEXT:
    {related_concepts}
    
    SOURCE DOCUMENT:
    {doc_summary}
    
    Generate a comprehensive build plan with:
    - Full overview and value proposition
    - Complete tech stack requirements
    - Step-by-step implementation guide
    - Starter code
    - Learning resources
    ...
    """
    
    full_plan = await call_gpt_5(prompt, max_tokens=15000)
    
    # Cache the expanded plan
    db.add(ExpandedBuildPlan(
        seed_id=seed_id,
        content=full_plan
    ))
    
    return full_plan
```

---

## 📊 Comparison Table

| Feature | Quick Ideas | Expand Seed | What Can I Build |
|---------|-------------|-------------|------------------|
| **Data Source** | `build_idea_seeds` | Seed + related concepts | All concepts (KB-wide) |
| **AI Calls** | None | 1 (expansion) | 1 (synthesis) |
| **Speed** | <100ms | 8-15s | 20-30s |
| **Cost** | $0 | $0.05-0.10 | $0.20-0.50 |
| **Results** | 10-20 seeds | 1 detailed plan | 3-5 detailed plans |
| **Scope** | Single-doc focused | Focused + context | Cross-doc synthesis |
| **Quality** | Good | Very Good | Excellent |
| **Use Case** | Browse & explore | Focused development | Comprehensive analysis |

---

## 🎯 User Journey Examples

### **Journey 1: Quick Explorer**
```
1. User clicks "Quick Ideas"
2. Sees 12 seed cards instantly
3. Clicks "Expand This" on interesting seed
4. Gets full build plan in 10s
5. Downloads markdown and starts building
```

**Cost:** $0.08 total  
**Time:** 10 seconds

---

### **Journey 2: Deep Analyzer**
```
1. User clicks "What Can I Build?"
2. Waits 25 seconds
3. Gets 4 comprehensive, cross-document build plans
4. Reviews all options
5. Picks best one and starts building
```

**Cost:** $0.35 total  
**Time:** 25 seconds

---

### **Journey 3: Hybrid Approach**
```
1. User browses Quick Ideas (free, instant)
2. Finds 3 interesting seeds
3. Expands each one ($0.24 total, 30s total)
4. Compares expanded plans
5. Also runs "What Can I Build?" to see cross-doc ideas ($0.40)
6. Now has 7 options to choose from
```

**Cost:** $0.64 total  
**Time:** ~60 seconds  
**Result:** Maximum exploration with reasonable cost

---

## 💡 Why This Is Better

### **Addresses Original Concerns:**

1. ✅ **Seed Dependency Issue** - Seeds used appropriately (quick exploration, not forced into deep analysis)
2. ✅ **Cost Control** - Users choose their cost/quality tradeoff
3. ✅ **Speed Options** - Instant, fast, or thorough
4. ✅ **KB Utilization** - All tracks leverage KB appropriately

### **Benefits:**

- **Flexibility** - Different workflows for different needs
- **Progressive Enhancement** - Start cheap/fast, go deep when needed
- **Seed Value** - Ingestion cost (~$0.01/doc) pays off across multiple use cases
- **User Choice** - Let users decide speed vs depth tradeoff

### **Trade-offs:**

- **More Complexity** - Three endpoints instead of one
- **UI Design** - Need clear explanation of what each does
- **Caching Strategy** - Should cache expanded seeds to avoid re-generating

---

## 🚀 Recommended Implementation Order

### **Phase 1: Foundation (Current State)**
- ✅ Seed generation working (Stage 8)
- ✅ `/what_can_i_build` working with fallback
- ✅ Concepts stored in `document_summaries.key_concepts`

### **Phase 2: Quick Ideas** (2-4 hours)
```python
# Simple database query endpoint
GET /quick-ideas
- Query build_idea_seeds table
- Add basic filtering (difficulty, date)
- Return JSON array
```

### **Phase 3: Expand Seed** (6-8 hours)
```python
# New endpoint with KB context
POST /expand-seed/{seed_id}
- Fetch seed from DB
- Query related concepts
- Call GPT-5 with focused prompt
- Cache result
```

### **Phase 4: UI Updates** (4-6 hours)
- Add "Quick Ideas" section to dashboard
- Add "Expand This" button to seed cards
- Update "What Can I Build?" button with explanation
- Add cost/time estimates to each option

### **Phase 5: Optimization** (ongoing)
- Cache expanded plans
- Add seed rating/feedback
- Improve related concept finding
- Add cross-seed comparisons

---

## 📝 Database Schema Changes

### **New Table: `expanded_build_plans`**

```sql
CREATE TABLE expanded_build_plans (
    id SERIAL PRIMARY KEY,
    seed_id INTEGER REFERENCES build_idea_seeds(id) ON DELETE CASCADE,
    content JSONB NOT NULL,
    token_count INTEGER,
    cost_usd DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW(),
    accessed_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP
);

CREATE INDEX idx_expanded_plans_seed ON expanded_build_plans(seed_id);
```

**Purpose:** Cache expanded seeds to avoid regenerating them

---

## 🎨 UI Mock-ups

### **Dashboard Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  SyncBoard 3.0 - Build Ideas                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Choose Your Path:                                      │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ ⚡ Quick     │  │ 🎯 Focused   │  │ 🔬 Deep      │   │
│  │   Ideas      │  │   Expansion  │  │   Analysis   │   │
│  │              │  │              │  │              │   │
│  │ Instant      │  │ 10-15s       │  │ 20-30s       │   │
│  │ Free         │  │ $0.08        │  │ $0.35        │   │
│  │              │  │              │  │              │   │
│  │ [Browse →]   │  │ [Expand →]   │  │ [Analyze →]  │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│  Recent Quick Ideas:                                    │
│  • API Gateway Service (Intermediate)                   │
│  • Video Pipeline (Advanced)                            │
│  • SEO Agent Platform (Intermediate)                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔮 Future Enhancements

### **Seed Quality Tracking:**
- Track which seeds get expanded
- Track which expanded plans lead to actual projects
- Use feedback to improve Stage 8 seed generation

### **Smart Recommendations:**
```python
# Recommend which track based on user behavior
if user.recent_expansions > 5:
    suggest = "expand_seed"  # User likes focused approach
elif user.kb_documents > 50:
    suggest = "what_can_i_build"  # Large KB = cross-doc value
else:
    suggest = "quick_ideas"  # New user = browse first
```

### **Hybrid Queries:**
```python
# "Show me seeds related to THIS expanded plan"
# "Generate deep analysis focused on THESE seed themes"
```

---

## ✅ Conclusion

**Don't force users to choose between seeds or KB - give them THREE complementary tools:**

1. **Quick Ideas** - Free, instant browsing
2. **Expand Seed** - Focused, affordable depth  
3. **What Can I Build** - Comprehensive, expensive synthesis

**This architecture:**
- ✅ Respects user time and money
- ✅ Keeps seed generation valuable
- ✅ Fully utilizes KB
- ✅ Provides clear paths for different needs

**Next Step:** Implement Quick Ideas endpoint first (simplest), then Expand Seed, then refine What Can I Build.

---

*Document Created: December 4, 2025*  
*SyncBoard 3.0 Architecture Planning*
