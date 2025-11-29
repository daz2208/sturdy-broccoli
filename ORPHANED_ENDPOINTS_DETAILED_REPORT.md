# DETAILED ORPHANED ENDPOINTS REPORT

## Summary
- **Total Router Files:** 29
- **Total Endpoints Defined:** 202
- **Endpoints Called by Frontend:** 122
- **Orphaned Endpoints (0% usage):** 80
- **Routers at 0% Usage:** 2 (content_generation.py, websocket.py)

---

## PRIORITY ANALYSIS: 0% USAGE ROUTERS

### Router: content_generation.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/content_generation.py`
- **Total Endpoints:** 8
- **Used:** 0 (0%)
- **Status:** COMPLETELY ORPHANED - No frontend usage at all

**ORPHANED ENDPOINTS (All 8):**
- GET /content/industries
- GET /content/kb-industry
- GET /content/templates/{industry}
- POST /content/detect-industry
- POST /content/generate
- POST /content/generate/analysis
- POST /content/generate/summary
- PUT /content/kb-industry

---

### Router: websocket.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/websocket.py`
- **Total Endpoints:** 2
- **Used:** 0 (0%)
- **Status:** COMPLETELY ORPHANED - No frontend usage at all

**ORPHANED ENDPOINTS (All 2):**
- GET /ws/presence/{doc_id}
- GET /ws/status

---

## ROUTERS WITH HIGHEST ORPHANED RATES

### Router: feedback.py (NEWLY FIXED)
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/feedback.py`
- **Total Endpoints:** 13
- **Used:** 6 (46%)
- **Orphaned:** 7 (54%)
- **Status:** Recently added - many features not yet integrated to frontend

**ORPHANED ENDPOINTS:**
1. GET /feedback/decisions/document/{document_id} - Get AI decision history for specific document
2. GET /feedback/metrics - Get comprehensive learning metrics for user
3. GET /feedback/patterns - Get user's feedback patterns and preferences
4. GET /feedback/pending - Get low-confidence decisions needing validation
5. POST /feedback/cluster-move - Record when user moves document to different cluster
6. POST /feedback/concept-edit - Record when user edits extracted concepts
7. POST /feedback/validate - Explicitly validate or reject an AI decision

**ENDPOINTS USED:**
1. GET /feedback/validation-prompts - Get validation prompts with user-friendly format
2. GET /feedback/low-confidence-decisions - Get low-confidence AI decisions (Phase D)
3. GET /feedback/accuracy-metrics - Get overall accuracy metrics across all decision types
4. GET /feedback/accuracy - Get accuracy metrics for AI decisions by type
5. POST /feedback/submit - Submit user feedback for an AI decision
6. GET /feedback/user-feedback - Get all user feedback submitted

---

### Router: learning.py (NEWLY FIXED)
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/learning.py`
- **Total Endpoints:** 19
- **Used:** 13 (68%)
- **Orphaned:** 6 (32%)
- **Status:** Recently added - core learning operations not fully exposed to frontend

**ORPHANED ENDPOINTS:**
1. GET /learning/profile - Get user's learning profile with calibrated thresholds
2. GET /learning/status - Get comprehensive learning status for current user
3. POST /learning/agent/trigger/{task_name} - Manually trigger autonomous agent task
4. POST /learning/calibrate - Calibrate confidence thresholds based on historical accuracy
5. POST /learning/maverick/trigger/{task_name} - Manually trigger Maverick agent task
6. POST /learning/run - Trigger learning from unprocessed feedback

**ENDPOINTS USED:**
1. GET /learning/rules - Get user's learned rules
2. DELETE /learning/rules/{rule_id} - Deactivate a learned rule
3. PUT /learning/rules/{rule_id}/reactivate - Reactivate a previously deactivated rule
4. GET /learning/vocabulary - Get user's concept vocabulary
5. POST /learning/vocabulary - Manually add a vocabulary term
6. DELETE /learning/vocabulary/{vocab_id} - Delete a vocabulary term
7. GET /learning/agent/status - Get autonomous Learning Agent's status
8. GET /learning/agent/decisions - Get recent autonomous decisions made by agent
9. GET /learning/maverick/status - Get Maverick Agent's status and personality
10. GET /learning/maverick/hypotheses - Get Maverick's improvement hypotheses
11. GET /learning/maverick/insights - Get Maverick's learning insights
12. GET /learning/maverick/activity - Get Maverick's recent activity log
13. GET /learning/agents/overview - Get combined overview of all agents

---

### Router: knowledge_graph.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/knowledge_graph.py`
- **Total Endpoints:** 8
- **Used:** 5 (62%)
- **Orphaned:** 3 (38%)

**ORPHANED ENDPOINTS:**
1. GET /knowledge-graph/by-concept/{concept} - Find documents that cover a specific concept
2. GET /knowledge-graph/by-tech/{technology} - Find documents that use a specific technology
3. GET /knowledge-graph/related/{doc_id} - Get documents related to a specific document

**ENDPOINTS USED:**
1. GET /knowledge-graph/stats - Get statistics about the knowledge graph
2. POST /knowledge-graph/build - Build or rebuild the knowledge graph
3. GET /knowledge-graph/concepts - Get top concepts across all documents
4. GET /knowledge-graph/technologies - Get top technologies across all documents
5. GET /knowledge-graph/path - Find a learning path from one concept to another

---

### Router: knowledge_tools.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/knowledge_tools.py`
- **Total Endpoints:** 12
- **Used:** 10 (83%)
- **Orphaned:** 2 (17%)

**ORPHANED ENDPOINTS:**
1. GET /knowledge/quality/{doc_id} - Score document quality metrics
2. POST /knowledge/flashcards/{doc_id} - Generate flashcards for specific document

**ENDPOINTS USED:**
1. GET /knowledge/gaps - Analyze knowledge gaps in KB
2. GET /knowledge/status - Get knowledge tools status
3. POST /knowledge/chat - Knowledge-aware chat interface
4. POST /knowledge/compare - Compare two documents
5. POST /knowledge/debug - Debug errors with knowledge context
6. POST /knowledge/eli5 - Explain topic in simple terms
7. POST /knowledge/interview-prep - Generate interview prep materials
8. POST /knowledge/learning-path - Optimize learning path for goal
9. POST /knowledge/generate-code - Generate code from knowledge base
10. GET /knowledge/digest - Get weekly digest of new knowledge

---

### Router: teams.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/teams.py`
- **Total Endpoints:** 16
- **Used:** 15 (93%)
- **Orphaned:** 1 (6%)

**ORPHANED ENDPOINTS:**
1. POST /teams/invitations/{token}/accept - Accept team invitation by token

---

### Router: documents.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/documents.py`
- **Total Endpoints:** 7
- **Used:** 7 (100%)
- **Status:** FULLY INTEGRATED - All endpoints used

---

### Router: duplicates.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/duplicates.py`
- **Total Endpoints:** 3
- **Used:** 3 (100%)
- **Status:** FULLY INTEGRATED - All endpoints used

---

### Router: admin.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/admin.py`
- **Total Endpoints:** 5
- **Used:** 2 (40%)
- **Orphaned:** 3 (60%)

**ORPHANED ENDPOINTS:**
1. GET /admin/llm-provider - Get current LLM provider status
2. POST /admin/llm-provider/test - Test LLM provider connection
3. POST /admin/reprocess-document/{doc_id} - Reprocess a document

**ENDPOINTS USED:**
1. GET /admin/chunk-status - Get document chunking status
2. POST /admin/backfill-chunks - Backfill chunks for documents

---

### Router: build_suggestions.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/build_suggestions.py`
- **Total Endpoints:** 13
- **Used:** 11 (84%)
- **Orphaned:** 2 (15%)

**ORPHANED ENDPOINTS:**
1. GET /quick-ideas - Get quick project ideas
2. POST /validate-market - Validate market potential of idea

---

### Router: generated_code.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/generated_code.py`
- **Total Endpoints:** 8
- **Used:** 4 (50%)
- **Orphaned:** 4 (50%)

**ORPHANED ENDPOINTS:**
1. GET /generated-code/project/{project_id}/files - Get project code files
2. GET /generated-code/project/{project_id}/zip - Download project as ZIP
3. POST /generated-code/store - Store generated code
4. POST /generated-code/store-batch - Store multiple generated codes

---

### Router: integrations.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/integrations.py`
- **Total Endpoints:** 8
- **Used:** 6 (75%)
- **Orphaned:** 2 (25%)

**ORPHANED ENDPOINTS:**
1. GET /integrations/health - Health check for integrations
2. POST /integrations/github/import - Import GitHub repository

---

### Router: auth.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/auth.py`
- **Total Endpoints:** 4
- **Used:** 2 (50%)
- **Orphaned:** 2 (50%)

**ORPHANED ENDPOINTS:**
1. GET /auth/{provider}/callback - OAuth provider callback handler
2. GET /auth/{provider}/login - OAuth provider login redirect

---

### Router: ai_generation.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/ai_generation.py`
- **Total Endpoints:** 3
- **Used:** 2 (66%)
- **Orphaned:** 1 (17%)

**ORPHANED ENDPOINTS:**
1. GET /generate/status - Get generation job status

---

### Router: clusters.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/clusters.py`
- **Total Endpoints:** 5
- **Used:** 4 (80%)
- **Orphaned:** 1 (8%)

**ORPHANED ENDPOINTS:**
1. GET /export/cluster/{cluster_id} - Export single cluster

---

### Router: project_goals.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/project_goals.py`
- **Total Endpoints:** 7
- **Used:** 6 (85%)
- **Orphaned:** 1 (14%)

**ORPHANED ENDPOINTS:**
1. POST /project-goals/set-primary/{goal_id} - Set primary goal

---

### Router: usage.py
**Path:** `/home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend/backend/routers/usage.py`
- **Total Endpoints:** 6
- **Used:** 5 (83%)
- **Orphaned:** 1 (17%)

**ORPHANED ENDPOINTS:**
1. POST /usage/upload - Track upload usage

---

## FULLY INTEGRATED ROUTERS (100% Usage)

- **analytics.py** - 1/1 endpoints
- **documents.py** - 7/7 endpoints
- **duplicates.py** - 3/3 endpoints
- **jobs.py** - 3/3 endpoints
- **knowledge_bases.py** - 11/11 endpoints
- **n8n_workflows.py** - 7/7 endpoints
- **project_tracking.py** - 10/10 endpoints
- **relationships.py** - 4/4 endpoints
- **saved_searches.py** - 4/4 endpoints
- **search.py** - 3/3 endpoints
- **tags.py** - 6/6 endpoints
- **uploads.py** - 6/6 endpoints

---

## KEY FINDINGS

### Newly Fixed Routers (Not Yet Fully Exposed)
1. **feedback.py** - 7/13 endpoints orphaned (54% missing)
2. **learning.py** - 6/19 endpoints orphaned (32% missing)

These routers were recently fixed to be properly importable but the frontend has not yet implemented all available endpoints.

### Completely Unused Routers
1. **content_generation.py** - 0/8 endpoints (100% orphaned)
2. **websocket.py** - 0/2 endpoints (100% orphaned)

These routers should either be integrated into the frontend or removed if no longer needed.

### High Orphan Rates (>40%)
1. **feedback.py** - 54% orphaned
2. **generated_code.py** - 50% orphaned
3. **admin.py** - 60% orphaned
4. **auth.py** - 50% orphaned

---

## RECOMMENDATIONS

1. **Immediate Action (High Priority):**
   - Integrate `content_generation.py` endpoints or deprecate the router
   - Implement `websocket.py` endpoints or remove the router
   - Expose additional `feedback.py` endpoints for learning validation UI
   - Expose additional `learning.py` endpoints for agent management UI

2. **Medium Priority:**
   - Implement `generated_code.py` file management endpoints
   - Expose `admin.py` provider management endpoints
   - Add OAuth callback handlers from `auth.py`

3. **Low Priority (Nice to Have):**
   - Add market validation endpoint to `build_suggestions.py`
   - Expose document quality scoring endpoint
   - Add health check endpoint for integrations

