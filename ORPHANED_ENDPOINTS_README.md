# Orphaned Endpoints Analysis

This directory contains a comprehensive analysis of endpoints across all 29 routers in the SyncBoard 3.0 backend.

## Files in This Analysis

### 1. ORPHANED_ENDPOINTS_EXECUTIVE_SUMMARY.md
**Purpose:** High-level overview with actionable recommendations
- Key metrics and findings
- Critical issues requiring immediate action
- Action plan with prioritized phases
- Recommendations by priority level

**Best For:** Quick decision-making, understanding the big picture, priority planning

**Length:** ~6 KB, 5-10 minute read

---

### 2. ORPHANED_ENDPOINTS_DETAILED_REPORT.md
**Purpose:** Complete detailed breakdown of every router and its endpoints
- All 29 routers listed with endpoint counts
- Each router's used and orphaned endpoints explicitly listed
- Descriptions of what each endpoint does
- Organized by priority and usage level

**Best For:** Developers implementing integrations, detailed understanding, reference

**Length:** ~13 KB, 20-30 minute read

---

### 3. ORPHANED_ENDPOINTS_QUICK_REFERENCE.txt
**Purpose:** Fast lookup tables and visual summary
- Quick reference table of all routers
- Usage statistics and percentages
- Visual tree structure of orphaned endpoints
- Summary statistics

**Best For:** Quick lookups during development, presenting to teams

**Length:** ~6 KB, 5-10 minute read

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Routers | 29 |
| Total Endpoints | 202 |
| Currently Used | 122 (60%) |
| Orphaned | 80 (40%) |
| **0% Usage Routers** | 2 (content_generation.py, websocket.py) |
| **100% Usage Routers** | 12 (well integrated) |

---

## Critical Issues Found

### Routers at 0% Usage (Complete Orphans)
1. **content_generation.py** - 8 endpoints (never called)
2. **websocket.py** - 2 endpoints (never called)

### Newly Fixed Routers (Partially Integrated)
1. **feedback.py** - 7/13 endpoints orphaned (54%)
2. **learning.py** - 6/19 endpoints orphaned (32%)

---

## Recommended Actions (By Priority)

### Phase 1: Immediate (This Week)
1. Decide on content_generation.py (integrate or remove)
2. Decide on websocket.py (implement or remove)
3. Expose feedback.py missing endpoints (7 endpoints)
4. Expose learning.py missing endpoints (6 endpoints)

### Phase 2: Short-Term
5. Integrate generated_code.py file management (4 endpoints)
6. Add admin.py provider management UI (3 endpoints)
7. Complete OAuth in auth.py (2 endpoints)
8. Expose knowledge graph navigation (3 endpoints)

### Phase 3: Medium-Term
9. Market validation endpoint
10. Document quality scoring
11. Remaining minor endpoints

---

## How to Use These Files

**For a Quick Overview:**
1. Read EXECUTIVE_SUMMARY.md (5-10 min)
2. Skim QUICK_REFERENCE.txt table (3 min)

**For Implementation:**
1. Read EXECUTIVE_SUMMARY.md for context
2. Find your router in DETAILED_REPORT.md
3. Use QUICK_REFERENCE.txt for quick lookups
4. Reference endpoint descriptions for implementation details

**For Presentations:**
1. Use metrics from EXECUTIVE_SUMMARY.md
2. Show charts/tables from QUICK_REFERENCE.txt
3. Link to DETAILED_REPORT.md for deep dives

---

## Analysis Methodology

### Data Collection
- Scanned all 29 router files in `/backend/routers/`
- Extracted endpoint definitions using regex pattern matching for `@router.get/post/put/delete/patch` decorators
- Parsed router prefixes and full endpoint paths

### Frontend Analysis
- Analyzed complete API client in `/frontend/src/lib/api.ts`
- Extracted all API calls using pattern matching
- Matched backend endpoints against frontend calls

### Classification
- **Used Endpoints:** Called by at least one frontend API method
- **Orphaned Endpoints:** Defined in backend but never called by frontend
- **0% Usage:** Routers with zero endpoints called

### Accuracy
- Pattern matching with high precision
- Includes endpoints with path parameters (e.g., {doc_id}, {task_name})
- Handles multiple HTTP methods per path
- Conservative matching (requires explicit frontend call)

---

## Next Steps

1. **Review** these documents and share with team
2. **Prioritize** which Phase 1 items to tackle first
3. **Implement** API integration for high-priority endpoints
4. **Test** thoroughly before committing
5. **Track** progress against Phase milestones

---

## Questions?

Each document includes:
- Detailed file paths for backend routers
- Complete endpoint definitions
- Descriptions of what each endpoint does
- Implementation recommendations

For specific routers or endpoints, consult DETAILED_REPORT.md.

---

**Analysis Date:** 2025-11-29
**Status:** Complete and Ready for Action
**Contact:** Review findings with team leads
