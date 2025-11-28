# 🤖 AI Agent Implementation Plan - Option D (Complete)

**Project:** SyncBoard 3.0 - Make AI Agents Fully Functional & Interactive
**Created:** 2025-11-28
**Status:** AWAITING APPROVAL

---

## 📋 EXECUTIVE SUMMARY

**Goal:** Transform hidden AI agents into visible, interactive, and useful assistants that learn from your behavior and actively help you work.

**Current State:**
- ✅ Agents working (Learning Agent + Maverick Agent)
- ✅ Collecting data (20 observations, 7 AI decisions, 3 vocabulary terms)
- ❌ No user interface (invisible)
- ❌ No feedback loop (can't learn from you)
- ❌ No interaction (just consuming tokens)

**Target State:**
- ✅ Visible dashboard showing agent activity
- ✅ Automatic feedback capture from your edits
- ✅ Interactive validation of AI decisions
- ✅ Inline suggestions in your workflow
- ✅ Agents continuously improving based on your patterns

**Total Estimated Time:** 6-8 days (can be done incrementally)

---

## 🎯 IMPLEMENTATION PHASES

### **Phase 1: Feedback Capture System** ⭐ CRITICAL
**Time:** 1-2 days
**Priority:** HIGH
**Goal:** Let agents learn from your actions automatically

### **Phase 2: Agent Dashboard UI** ⭐ HIGH VALUE
**Time:** 2-3 days
**Priority:** HIGH
**Goal:** See what agents are doing and validate decisions

### **Phase 3: Inline Agent Integration** 🚀 BEST UX
**Time:** 1-2 days
**Priority:** MEDIUM
**Goal:** Agents assist in your workflow

### **Phase 4: Analytics & Optimization** 📊 POLISH
**Time:** 1 day
**Priority:** LOW
**Goal:** Fine-tune agent performance

---

# 📝 DETAILED TASK BREAKDOWN

---

## **PHASE 1: FEEDBACK CAPTURE SYSTEM** (Backend)

### **Task 1.1: Create Feedback Router**
**File:** `backend/routers/feedback.py` (NEW FILE)
**Time:** 2 hours

**Code to add:**
```python
"""
Feedback Router - Capture user corrections for AI learning.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..models import User
from ..dependencies import get_current_user
from ..database import get_db
from ..db_models import DBUserFeedback, DBAIDecision

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("/concept-edit")
async def capture_concept_edit(
    document_id: int,
    original_concepts: list[str],
    edited_concepts: list[str],
    ai_decision_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Capture when user edits concepts extracted by AI.

    Tracks:
    - Removed concepts (in original, not in edited)
    - Added concepts (in edited, not in original)
    - Renamed concepts (if pattern detected)
    """
    removed = set(original_concepts) - set(edited_concepts)
    added = set(edited_concepts) - set(original_concepts)

    if removed or added:
        feedback = DBUserFeedback(
            feedback_type="concept_edit",
            username=current_user.username,
            document_id=document_id,
            ai_decision_id=ai_decision_id,
            original_value={"concepts": original_concepts},
            new_value={"concepts": edited_concepts},
            context={
                "removed": list(removed),
                "added": list(added)
            },
            processed=False,
            created_at=datetime.utcnow()
        )
        db.add(feedback)
        db.commit()

    return {
        "success": True,
        "removed_count": len(removed),
        "added_count": len(added)
    }

@router.post("/cluster-change")
async def capture_cluster_change(
    document_id: int,
    original_cluster_id: Optional[int],
    new_cluster_id: int,
    ai_decision_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Capture when user changes document cluster assignment.
    """
    feedback = DBUserFeedback(
        feedback_type="cluster_change",
        username=current_user.username,
        document_id=document_id,
        ai_decision_id=ai_decision_id,
        original_value={"cluster_id": original_cluster_id},
        new_value={"cluster_id": new_cluster_id},
        processed=False,
        created_at=datetime.utcnow()
    )
    db.add(feedback)
    db.commit()

    return {"success": True}

@router.post("/ai-decision/{decision_id}/validate")
async def validate_ai_decision(
    decision_id: int,
    validated: bool,
    correction: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    User validates or rejects an AI decision.
    """
    decision = db.query(DBAIDecision).filter_by(
        id=decision_id,
        username=current_user.username
    ).first()

    if not decision:
        raise HTTPException(404, "Decision not found")

    decision.validated = True
    decision.validation_result = "correct" if validated else "incorrect"
    decision.validation_timestamp = datetime.utcnow()

    if not validated and correction:
        # Store correction as feedback
        feedback = DBUserFeedback(
            feedback_type="ai_decision_correction",
            username=current_user.username,
            document_id=decision.document_id,
            ai_decision_id=decision_id,
            original_value=decision.output_data,
            new_value=correction,
            processed=False,
            created_at=datetime.utcnow()
        )
        db.add(feedback)

    db.commit()

    return {"success": True, "validated": validated}
```

**Acceptance Criteria:**
- [ ] Endpoint `/feedback/concept-edit` works
- [ ] Endpoint `/feedback/cluster-change` works
- [ ] Endpoint `/feedback/ai-decision/{id}/validate` works
- [ ] Feedback stored in `user_feedback` table
- [ ] Linked to `ai_decisions` when applicable

---

### **Task 1.2: Modify Documents Router**
**File:** `backend/routers/documents.py`
**Time:** 1 hour

**Changes needed:**
```python
# Add at top
from .feedback import capture_concept_edit

# In PUT /documents/{doc_id} endpoint, after successful update:
@router.put("/{doc_id}")
async def update_document(...):
    # ... existing update logic ...

    # NEW: Auto-capture concept changes
    if old_concepts != new_concepts:
        await capture_concept_edit(
            document_id=doc_id,
            original_concepts=old_concepts,
            edited_concepts=new_concepts,
            ai_decision_id=None,  # TODO: Link if we have decision_id
            current_user=current_user,
            db=db
        )

    return updated_document
```

**Acceptance Criteria:**
- [ ] Editing document concepts triggers feedback capture
- [ ] No errors when concepts unchanged
- [ ] Feedback appears in database after edit

---

### **Task 1.3: Modify Clusters Router**
**File:** `backend/routers/clusters.py`
**Time:** 1 hour

**Changes needed:**
```python
# Add at top
from .feedback import capture_cluster_change

# In PUT /clusters/{cluster_id}/documents endpoint:
@router.put("/{cluster_id}/documents")
async def move_document_to_cluster(...):
    # ... existing move logic ...

    # NEW: Auto-capture cluster changes
    await capture_cluster_change(
        document_id=doc_id,
        original_cluster_id=old_cluster_id,
        new_cluster_id=cluster_id,
        current_user=current_user,
        db=db
    )

    return result
```

**Acceptance Criteria:**
- [ ] Moving document to different cluster triggers feedback
- [ ] Feedback includes old and new cluster IDs
- [ ] No performance degradation

---

### **Task 1.4: Mount Feedback Router**
**File:** `backend/main.py`
**Time:** 5 minutes

**Changes needed:**
```python
# Add import
from backend.routers import feedback

# Mount router
app.include_router(feedback.router)
```

**Acceptance Criteria:**
- [ ] `/feedback/*` endpoints accessible
- [ ] Shows in API docs at `/docs`

---

### **Task 1.5: Test Feedback Capture**
**File:** `tests/test_feedback.py` (NEW FILE)
**Time:** 1 hour

**Tests to write:**
```python
def test_concept_edit_feedback():
    """Test concept edit feedback is captured"""

def test_cluster_change_feedback():
    """Test cluster change feedback is captured"""

def test_ai_decision_validation():
    """Test validating AI decisions"""
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Feedback captured correctly in test scenarios
- [ ] Edge cases handled (empty concepts, null values, etc.)

---

## **PHASE 2: AGENT DASHBOARD UI** (Frontend)

### **Task 2.1: Create Agent Dashboard Page**
**File:** `frontend/pages/agents.tsx` (NEW FILE if Next.js) or `frontend/src/pages/Agents.jsx` (if React)
**Time:** 3 hours

**Structure:**
```typescript
import React, { useState, useEffect } from 'react';
import { LearningAgentCard } from '../components/LearningAgentCard';
import { MaverickAgentCard } from '../components/MaverickAgentCard';
import { VocabularyList } from '../components/VocabularyList';
import { AIDecisionValidator } from '../components/AIDecisionValidator';
import { LearningProgress } from '../components/LearningProgress';

export default function AgentsPage() {
  const [learningStatus, setLearningStatus] = useState(null);
  const [maverickStatus, setMaverickStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgentData();
    const interval = setInterval(fetchAgentData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchAgentData = async () => {
    try {
      const token = getAuthToken();

      // Fetch learning status
      const learningRes = await fetch('/learning/status', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const learningData = await learningRes.json();
      setLearningStatus(learningData);

      // Fetch maverick status (TODO: create endpoint)
      // const maverickRes = await fetch('/agents/maverick/status', ...);

      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch agent data:', error);
    }
  };

  if (loading) return <div>Loading agents...</div>;

  return (
    <div className="agents-dashboard">
      <h1>🤖 AI Agents Dashboard</h1>

      <div className="agent-cards">
        <LearningAgentCard data={learningStatus} />
        <MaverickAgentCard data={maverickStatus} />
      </div>

      <div className="agent-sections">
        <VocabularyList vocabulary={learningStatus?.vocabulary} />
        <AIDecisionValidator />
        <LearningProgress data={learningStatus} />
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Page renders without errors
- [ ] Fetches agent data on load
- [ ] Auto-refreshes every 30 seconds
- [ ] Shows loading state
- [ ] Handles errors gracefully

---

### **Task 2.2: Create Learning Agent Card Component**
**File:** `frontend/components/LearningAgentCard.tsx`
**Time:** 1 hour

**Component:**
```typescript
export function LearningAgentCard({ data }) {
  if (!data) return <div>Loading...</div>;

  const { status, mode, total_observations, total_actions,
          autonomous_decisions, last_action } = data;

  return (
    <div className="agent-card learning-agent">
      <div className="card-header">
        <h2>🧠 Learning Agent</h2>
        <span className="status-badge">{status}</span>
      </div>

      <div className="card-body">
        <p className="mode">Mode: {mode}</p>

        <div className="stats-grid">
          <div className="stat">
            <span className="stat-value">{total_observations}</span>
            <span className="stat-label">Observations</span>
          </div>
          <div className="stat">
            <span className="stat-value">{total_actions}</span>
            <span className="stat-label">Actions Taken</span>
          </div>
          <div className="stat">
            <span className="stat-value">{autonomous_decisions}</span>
            <span className="stat-label">Autonomous</span>
          </div>
        </div>

        {last_action && (
          <div className="last-action">
            <h4>🎯 Last Action:</h4>
            <p>{formatAction(last_action)}</p>
            <small>{formatTime(last_action.timestamp)}</small>
          </div>
        )}
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Displays all agent stats
- [ ] Shows last action clearly
- [ ] Responsive design
- [ ] Updates when data changes

---

### **Task 2.3: Create Maverick Agent Card Component**
**File:** `frontend/components/MaverickAgentCard.tsx`
**Time:** 1.5 hours

**Component:**
```typescript
export function MaverickAgentCard({ data }) {
  const [selectedHypothesis, setSelectedHypothesis] = useState(null);

  const handleApprove = async (hypothesisId) => {
    // TODO: Call API to approve hypothesis
    await fetch(`/agents/maverick/hypotheses/${hypothesisId}/approve`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
  };

  return (
    <div className="agent-card maverick-agent">
      <div className="card-header">
        <h2>🎲 Maverick Agent</h2>
        <div className="personality">
          <span>Mood: {data.mood}</span>
          <span>Curiosity: {data.curiosity * 100}%</span>
          <span>Confidence: {data.confidence * 100}%</span>
        </div>
      </div>

      <div className="card-body">
        {data.active_hypothesis && (
          <div className="hypothesis">
            <h4>💡 Active Hypothesis:</h4>
            <div className="hypothesis-content">
              <p className="description">
                {data.active_hypothesis.description}
              </p>
              <p className="reasoning">
                <strong>Why:</strong> {data.active_hypothesis.reasoning}
              </p>
              <p className="status">
                Status: {data.active_hypothesis.status}
              </p>
            </div>

            <div className="hypothesis-actions">
              <button onClick={() => handleApprove(data.active_hypothesis.id)}>
                ✓ Approve Test
              </button>
              <button onClick={() => handleReject(data.active_hypothesis.id)}>
                ✗ Reject
              </button>
              <button onClick={() => setSelectedHypothesis(data.active_hypothesis)}>
                Details
              </button>
            </div>
          </div>
        )}

        <div className="stats">
          <p>Hypotheses: {data.hypotheses_proposed} proposed,
             {data.hypotheses_validated} validated</p>
        </div>
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Shows active hypothesis clearly
- [ ] Approve/Reject buttons work
- [ ] Shows personality traits
- [ ] Details modal works

---

### **Task 2.4: Create Vocabulary List Component**
**File:** `frontend/components/VocabularyList.tsx`
**Time:** 1 hour

**Component:**
```typescript
export function VocabularyList({ vocabulary }) {
  const [expanded, setExpanded] = useState({});

  const handleRemove = async (term) => {
    if (!confirm(`Remove "${term}" from learned vocabulary?`)) return;

    await fetch(`/learning/vocabulary/${term}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
  };

  return (
    <div className="vocabulary-section">
      <h3>📚 Learned Vocabulary ({vocabulary?.total || 0} terms)</h3>

      <div className="vocabulary-list">
        {vocabulary?.top_terms?.map(term => (
          <div key={term.canonical} className="vocabulary-item">
            <div className="term-header" onClick={() => toggleExpand(term.canonical)}>
              <span className="canonical">{term.canonical}</span>
              <span className="variant-count">{term.variants} variants</span>
            </div>

            {expanded[term.canonical] && (
              <div className="term-details">
                <ul className="variants">
                  {/* TODO: Fetch full variant list */}
                  <li>variant 1</li>
                  <li>variant 2</li>
                </ul>
                <div className="term-actions">
                  <button onClick={() => handleRemove(term.canonical)}>
                    Remove
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <button className="add-vocabulary">+ Add Custom Vocabulary</button>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Lists all learned vocabulary
- [ ] Shows variant count
- [ ] Expandable to see all variants
- [ ] Remove button works
- [ ] Add custom vocabulary button present

---

### **Task 2.5: Create AI Decision Validator Component**
**File:** `frontend/components/AIDecisionValidator.tsx`
**Time:** 2 hours

**Component:**
```typescript
export function AIDecisionValidator() {
  const [decisions, setDecisions] = useState([]);
  const [selectedDecision, setSelectedDecision] = useState(null);

  useEffect(() => {
    fetchUnvalidatedDecisions();
  }, []);

  const fetchUnvalidatedDecisions = async () => {
    const res = await fetch('/ai-decisions?validated=false', {
      headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
    const data = await res.json();
    setDecisions(data.decisions);
  };

  const handleValidate = async (decisionId, isCorrect) => {
    await fetch(`/feedback/ai-decision/${decisionId}/validate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ validated: isCorrect })
    });

    // Remove from list
    setDecisions(decisions.filter(d => d.id !== decisionId));
  };

  return (
    <div className="ai-decision-validator">
      <h3>🤖 Recent AI Decisions ({decisions.length} unvalidated)</h3>

      {decisions.length === 0 ? (
        <p>No pending decisions to validate</p>
      ) : (
        <div className="decision-list">
          {decisions.map(decision => (
            <div key={decision.id} className="decision-card">
              <div className="decision-header">
                <span className="decision-type">{decision.decision_type}</span>
                <span className="confidence">
                  {Math.round(decision.confidence_score * 100)}% confidence
                </span>
              </div>

              <div className="decision-content">
                {renderDecisionContent(decision)}
              </div>

              <div className="decision-actions">
                <button
                  className="validate-correct"
                  onClick={() => handleValidate(decision.id, true)}
                >
                  ✓ Correct
                </button>
                <button
                  className="validate-wrong"
                  onClick={() => handleValidate(decision.id, false)}
                >
                  ✗ Wrong
                </button>
                <button onClick={() => setSelectedDecision(decision)}>
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Fetches unvalidated AI decisions
- [ ] Displays decision details clearly
- [ ] Validate buttons work
- [ ] Decision removed from list after validation
- [ ] Details modal works

---

### **Task 2.6: Create Agent Endpoints (Backend)**
**File:** `backend/routers/agents.py` (NEW FILE)
**Time:** 2 hours

**Code:**
```python
"""
Agent Status Router - Get agent information.
"""
from fastapi import APIRouter, Depends
from ..models import User
from ..dependencies import get_current_user
from ..learning_agent import get_agent_status
from ..maverick_agent import get_maverick_status

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("/learning/status")
async def get_learning_agent_status(
    current_user: User = Depends(get_current_user)
):
    """Get Learning Agent status and metrics."""
    return get_agent_status()

@router.get("/maverick/status")
async def get_maverick_agent_status(
    current_user: User = Depends(get_current_user)
):
    """Get Maverick Agent status and active hypotheses."""
    return get_maverick_status()

@router.get("/ai-decisions")
async def get_ai_decisions(
    validated: bool = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI decisions, optionally filtered by validation status."""
    query = db.query(DBAIDecision).filter_by(username=current_user.username)

    if validated is not None:
        query = query.filter_by(validated=validated)

    decisions = query.order_by(DBAIDecision.created_at.desc()).limit(limit).all()

    return {
        "decisions": [
            {
                "id": d.id,
                "decision_type": d.decision_type,
                "confidence_score": d.confidence_score,
                "input_data": d.input_data,
                "output_data": d.output_data,
                "validated": d.validated,
                "created_at": d.created_at.isoformat()
            }
            for d in decisions
        ]
    }

@router.post("/maverick/hypotheses/{hypothesis_id}/approve")
async def approve_hypothesis(
    hypothesis_id: str,
    current_user: User = Depends(get_current_user)
):
    """Approve a Maverick hypothesis for implementation."""
    # TODO: Implement hypothesis approval logic
    return {"success": True, "message": "Hypothesis approved"}

@router.post("/maverick/hypotheses/{hypothesis_id}/reject")
async def reject_hypothesis(
    hypothesis_id: str,
    current_user: User = Depends(get_current_user)
):
    """Reject a Maverick hypothesis."""
    # TODO: Implement hypothesis rejection logic
    return {"success": True, "message": "Hypothesis rejected"}
```

**Acceptance Criteria:**
- [ ] All endpoints work
- [ ] Proper authentication
- [ ] Returns correct data
- [ ] Documented in API docs

---

### **Task 2.7: Add Navigation to Agents Page**
**File:** `frontend/components/Navigation.tsx` or main layout
**Time:** 15 minutes

**Changes:**
```typescript
<nav>
  {/* existing nav items */}
  <NavLink to="/agents">🤖 AI Agents</NavLink>
</nav>
```

**Acceptance Criteria:**
- [ ] Navigation link visible
- [ ] Links to agents page
- [ ] Highlighted when on agents page

---

### **Task 2.8: Style Agent Dashboard**
**File:** `frontend/styles/agents.css` (NEW FILE)
**Time:** 1 hour

**Styles needed:**
- Agent cards (learning, maverick)
- Vocabulary list
- Decision validator
- Progress indicators
- Responsive layout

**Acceptance Criteria:**
- [ ] Professional appearance
- [ ] Responsive design (mobile-friendly)
- [ ] Consistent with app theme
- [ ] Good contrast and readability

---

## **PHASE 3: INLINE AGENT INTEGRATION** (Frontend)

### **Task 3.1: Add Agent Suggestions to Document Viewer**
**File:** `frontend/components/DocumentViewer.tsx` or similar
**Time:** 2 hours

**Changes:**
```typescript
function DocumentViewer({ document }) {
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    // Fetch agent suggestions for this document
    fetchAgentSuggestions(document.id);
  }, [document.id]);

  const fetchAgentSuggestions = async (docId) => {
    const res = await fetch(`/agents/suggestions/${docId}`, {
      headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
    const data = await res.json();
    setSuggestions(data.suggestions);
  };

  return (
    <div className="document-viewer">
      {/* Show agent suggestions at top */}
      {suggestions.length > 0 && (
        <div className="agent-suggestions">
          <h4>🤖 AI Suggestions:</h4>
          {suggestions.map(suggestion => (
            <AgentSuggestion
              key={suggestion.id}
              suggestion={suggestion}
              onAccept={() => handleAcceptSuggestion(suggestion)}
              onReject={() => handleRejectSuggestion(suggestion)}
            />
          ))}
        </div>
      )}

      {/* existing document content */}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Suggestions display at document top
- [ ] Accept/Reject buttons work
- [ ] Non-intrusive design
- [ ] Can be dismissed

---

### **Task 3.2: Add Vocabulary Auto-complete**
**File:** `frontend/components/ConceptEditor.tsx` or concept input component
**Time:** 2 hours

**Changes:**
```typescript
function ConceptInput({ value, onChange }) {
  const [suggestions, setSuggestions] = useState([]);
  const [vocabulary, setVocabulary] = useState([]);

  useEffect(() => {
    // Load learned vocabulary
    fetchVocabulary();
  }, []);

  const handleInputChange = (input) => {
    onChange(input);

    // Filter vocabulary for suggestions
    const matches = vocabulary.filter(v =>
      v.canonical.toLowerCase().includes(input.toLowerCase()) ||
      v.variants.some(variant => variant.toLowerCase().includes(input.toLowerCase()))
    );
    setSuggestions(matches);
  };

  return (
    <div className="concept-input">
      <input
        value={value}
        onChange={e => handleInputChange(e.target.value)}
        placeholder="Enter concept..."
      />

      {suggestions.length > 0 && (
        <div className="autocomplete-dropdown">
          {suggestions.map(s => (
            <div
              key={s.canonical}
              className="suggestion-item"
              onClick={() => onChange(s.canonical)}
            >
              💡 {s.canonical}
              <small>(learned vocabulary)</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Auto-complete shows learned vocabulary
- [ ] Clicking suggestion fills input
- [ ] Works for both canonical and variant forms
- [ ] Doesn't interfere with normal typing

---

### **Task 3.3: Add Maverick Hypothesis Notifications**
**File:** `frontend/components/NotificationCenter.tsx` or create new
**Time:** 1.5 hours

**Component:**
```typescript
export function AgentNotifications() {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    // Poll for new agent notifications
    const interval = setInterval(fetchNotifications, 60000); // Every minute
    fetchNotifications();
    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async () => {
    const res = await fetch('/agents/notifications', {
      headers: { 'Authorization': `Bearer ${getAuthToken()}` }
    });
    const data = await res.json();
    setNotifications(data.notifications);
  };

  return (
    <div className="agent-notifications">
      {notifications.map(notif => (
        <div key={notif.id} className="notification">
          <div className="notif-icon">
            {notif.type === 'hypothesis' ? '🎲' : '🧠'}
          </div>
          <div className="notif-content">
            <strong>{notif.title}</strong>
            <p>{notif.message}</p>
          </div>
          <div className="notif-actions">
            <button onClick={() => handleView(notif)}>View</button>
            <button onClick={() => handleDismiss(notif.id)}>×</button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Notifications appear for new hypotheses
- [ ] Can view details
- [ ] Can dismiss notifications
- [ ] Persists dismissal state

---

### **Task 3.4: Create Agent Suggestion Endpoint (Backend)**
**File:** `backend/routers/agents.py` (modify existing)
**Time:** 1 hour

**Add:**
```python
@router.get("/suggestions/{document_id}")
async def get_document_suggestions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI agent suggestions for a specific document.
    """
    suggestions = []

    # Check for vocabulary suggestions
    # Check for cluster suggestions
    # Check for maverick hypotheses related to this document

    return {"suggestions": suggestions}

@router.get("/notifications")
async def get_agent_notifications(
    current_user: User = Depends(get_current_user)
):
    """
    Get pending agent notifications (new hypotheses, important findings).
    """
    notifications = []

    # Check for new maverick hypotheses
    # Check for learning milestones
    # Check for important observations

    return {"notifications": notifications}
```

**Acceptance Criteria:**
- [ ] Returns relevant suggestions for document
- [ ] Returns pending notifications
- [ ] Performant (< 200ms response time)

---

## **PHASE 4: ANALYTICS & OPTIMIZATION** (Polish)

### **Task 4.1: Create Learning Progress Component**
**File:** `frontend/components/LearningProgress.tsx`
**Time:** 2 hours

**Component:**
```typescript
export function LearningProgress({ data }) {
  return (
    <div className="learning-progress">
      <h3>📈 Learning Progress</h3>

      <div className="progress-metrics">
        <div className="metric">
          <label>Accuracy:</label>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${data?.profile?.accuracy_rate * 100}%` }}
            />
          </div>
          <span>{Math.round(data?.profile?.accuracy_rate * 100)}%</span>
        </div>

        <div className="metric">
          <label>Validated Decisions:</label>
          <span>{data?.profile?.total_decisions || 0}</span>
          {data?.profile?.total_decisions < 10 && (
            <small>Need 10+ for calibration</small>
          )}
        </div>

        <div className="metric">
          <label>Vocabulary Terms:</label>
          <span>{data?.vocabulary?.total || 0}</span>
        </div>

        <div className="metric">
          <label>Active Rules:</label>
          <span>{data?.rules?.total || 0}</span>
        </div>
      </div>

      <div className="recommendations">
        <h4>💡 To improve agents:</h4>
        <ul>
          <li>Validate AI decisions below</li>
          <li>Edit concepts and clusters</li>
          <li>Agents will learn from your patterns</li>
        </ul>
      </div>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Shows all key metrics
- [ ] Visual progress bars
- [ ] Recommendations displayed
- [ ] Updates in real-time

---

### **Task 4.2: Add Agent Settings Panel**
**File:** `frontend/components/AgentSettings.tsx` (NEW FILE)
**Time:** 2 hours

**Component:**
```typescript
export function AgentSettings() {
  const [settings, setSettings] = useState({
    aggressiveness: 'conservative',
    auto_apply_rules: false,
    confidence_threshold: 0.7,
    enable_maverick: true
  });

  const handleSave = async () => {
    await fetch('/agents/settings', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    });
  };

  return (
    <div className="agent-settings">
      <h3>⚙️ Agent Settings</h3>

      <div className="setting">
        <label>Agent Aggressiveness:</label>
        <select
          value={settings.aggressiveness}
          onChange={e => setSettings({...settings, aggressiveness: e.target.value})}
        >
          <option value="conservative">Conservative (fewer suggestions)</option>
          <option value="balanced">Balanced</option>
          <option value="aggressive">Aggressive (more suggestions)</option>
        </select>
      </div>

      <div className="setting">
        <label>
          <input
            type="checkbox"
            checked={settings.auto_apply_rules}
            onChange={e => setSettings({...settings, auto_apply_rules: e.target.checked})}
          />
          Auto-apply learned rules
        </label>
      </div>

      <div className="setting">
        <label>Confidence Threshold:</label>
        <input
          type="range"
          min="0.5"
          max="0.95"
          step="0.05"
          value={settings.confidence_threshold}
          onChange={e => setSettings({...settings, confidence_threshold: parseFloat(e.target.value)})}
        />
        <span>{Math.round(settings.confidence_threshold * 100)}%</span>
      </div>

      <div className="setting">
        <label>
          <input
            type="checkbox"
            checked={settings.enable_maverick}
            onChange={e => setSettings({...settings, enable_maverick: e.target.checked})}
          />
          Enable Maverick Agent (experimental features)
        </label>
      </div>

      <button onClick={handleSave}>Save Settings</button>
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] All settings adjustable
- [ ] Settings saved to backend
- [ ] Changes take effect immediately
- [ ] Validation on input values

---

### **Task 4.3: Add Export/Import Learned Rules**
**File:** `backend/routers/learning.py` (modify existing)
**Time:** 1 hour

**Add endpoints:**
```python
@router.get("/export")
async def export_learned_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all learned rules and vocabulary for backup/transfer.
    """
    rules = db.query(DBLearnedRule).filter_by(
        username=current_user.username
    ).all()

    vocabulary = db.query(DBConceptVocabulary).filter_by(
        username=current_user.username
    ).all()

    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "rules": [serialize_rule(r) for r in rules],
        "vocabulary": [serialize_vocab(v) for v in vocabulary]
    }

    return export_data

@router.post("/import")
async def import_learned_data(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import learned rules and vocabulary from export.
    """
    # Validate data format
    # Import rules
    # Import vocabulary
    # Return summary

    return {
        "success": True,
        "rules_imported": len(data.get("rules", [])),
        "vocabulary_imported": len(data.get("vocabulary", []))
    }
```

**Acceptance Criteria:**
- [ ] Export creates valid JSON
- [ ] Import validates data
- [ ] No duplicate entries created
- [ ] Handles errors gracefully

---

## 📊 TESTING & VALIDATION

### **Task T.1: Integration Testing**
**Time:** 2 hours

**Tests to write:**
1. End-to-end feedback capture flow
2. Agent dashboard loads correctly
3. AI decision validation works
4. Vocabulary auto-complete functional
5. Agent settings persist

**Files:**
- `tests/test_integration_agents.py`

---

### **Task T.2: User Acceptance Testing**
**Time:** 1 hour

**Checklist:**
- [ ] Can view agent dashboard
- [ ] Can see what agents learned
- [ ] Can validate AI decisions
- [ ] Can approve/reject hypotheses
- [ ] Can adjust agent settings
- [ ] Feedback captured automatically
- [ ] Vocabulary auto-complete works
- [ ] Suggestions appear in workflow

---

## 🚀 DEPLOYMENT CHECKLIST

### **Pre-deployment:**
- [ ] All tests passing
- [ ] Database migrations applied
- [ ] New endpoints documented
- [ ] Frontend builds without errors
- [ ] No console errors in browser

### **Deployment:**
- [ ] Backend deployed
- [ ] Frontend deployed
- [ ] Database backed up
- [ ] Celery workers restarted (to pick up new code)

### **Post-deployment:**
- [ ] Agents page accessible
- [ ] Feedback capture working
- [ ] No errors in logs
- [ ] Performance acceptable

---

## 📈 SUCCESS METRICS

After 1 week of use, we should see:
- [ ] 10+ AI decisions validated
- [ ] 5+ vocabulary terms learned
- [ ] 2+ learned rules created
- [ ] Agent accuracy improving
- [ ] User actively using agent dashboard

---

## 💰 RESOURCE REQUIREMENTS

**Development Time:**
- Phase 1: 1-2 days (8-16 hours)
- Phase 2: 2-3 days (16-24 hours)
- Phase 3: 1-2 days (8-16 hours)
- Phase 4: 1 day (8 hours)
- Testing: 0.5 days (4 hours)

**Total: 6-8.5 days (48-68 hours)**

**Infrastructure:**
- No additional servers needed
- Existing Celery workers handle agent tasks
- Database space: ~10MB for agent data

---

## 🔄 ROLLBACK PLAN

If issues arise:

1. **Phase 1 Rollback:**
   - Remove feedback router from main.py
   - Remove feedback capture calls from documents/clusters routers
   - Agents continue working, just no new feedback

2. **Phase 2 Rollback:**
   - Remove navigation link to agents page
   - Delete agents page route
   - Backend endpoints remain but unused

3. **Phase 3 Rollback:**
   - Remove inline suggestions code
   - Remove vocabulary auto-complete
   - Revert to previous component versions

4. **Full Rollback:**
   - Revert all code changes
   - Agents continue background work
   - No user-facing changes

---

## 📝 NOTES

- All changes are **additive** (no breaking changes to existing features)
- Can be implemented **incrementally** (phase by phase)
- Each phase provides **standalone value**
- Backward compatible with existing data
- No performance impact on existing features

---

## ✅ APPROVAL CHECKLIST

Before starting implementation, confirm:

- [ ] Plan reviewed and understood
- [ ] Time estimates acceptable
- [ ] Priorities aligned (can adjust phase order)
- [ ] Resources available
- [ ] Ready to proceed

---

**Status:** AWAITING YOUR APPROVAL
**Next Step:** Review plan → Approve → Begin Phase 1

**Questions? Concerns? Changes needed?**
Let me know what needs adjustment before we start!
