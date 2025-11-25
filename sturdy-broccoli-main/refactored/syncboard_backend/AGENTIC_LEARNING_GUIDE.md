# Agentic Learning System Guide

## Overview

The SyncBoard agentic learning system enables the AI to be self-aware, question its own decisions, and continuously improve through user feedback. This guide explains how the system works and how to use it.

## What Makes It "Agentic"?

**Agentic AI** means the AI actively monitors and improves itself, rather than just passively making predictions. Here's what makes this system agentic:

### 1. Self-Awareness (Phase B/C)
The AI knows when it's uncertain and tracks confidence scores for every decision:

```python
# When extracting concepts from a document
confidence_score = 0.68  # AI is only 68% confident

# If confidence < 75%, AI questions itself
if confidence < 0.75:
    # Phase C: AI critiques its own work
    critique = ai.critique_my_own_extraction()
    refined_result = ai.apply_critique()
```

### 2. Self-Critique (Phase C - Dual-Pass Extraction)
The AI literally reviews its own decisions using a dual-pass approach:

```
Pass 1: Extract concepts → ["Docker", "Kubernetes", "CI/CD"]

Pass 2: AI asks itself critical questions:
  - "Did I miss important concepts?"
  - "Are any concepts too vague?"
  - "Is my skill level assessment accurate?"
  - "Should I be more/less confident?"

Pass 3: Refine based on self-critique
  → ["Docker", "Kubernetes", "CI/CD", "Dockerfile", "docker-compose"]
  → Adjusted confidence: 0.68 → 0.72
```

### 3. Learning from Mistakes (Phase A)
Every decision and user correction is permanently recorded:

- **AI makes decision** → Stored in `ai_decisions` table with confidence score
- **User corrects it** → Stored in `user_feedback` table with reasoning
- **System analyzes patterns** → AI learns what it got wrong and why

### 4. Continuous Improvement
Over time, the AI:

- Tracks accuracy by confidence level ("When I'm 60% confident, I'm right 45% of the time")
- Learns user preferences ("User prefers more specific concept names")
- Gets better at knowing when to ask for help
- Improves confidence calibration

## System Architecture

### Four Phases

**Phase A - Foundation**
- Database tables: `ai_decisions`, `user_feedback`
- Feedback service for recording decisions and corrections
- API endpoints for feedback management

**Phase B - Wiring**
- Integrated feedback recording into all AI operations
- Every concept extraction, clustering, classification is tracked
- Automatic confidence scoring

**Phase C - Self-Critique**
- Dual-pass extraction with self-critique
- AI questions its own decisions before presenting to user
- Validation prompt generation in natural language

**Phase D - Frontend UI**
- Validation dashboard at `/ai-validation`
- User-friendly prompts for validation
- Accuracy metrics and improvement tracking
- Real-time feedback submission

## How It Works End-to-End

### Example Workflow: Document Upload

**1. User Uploads Document**
```
POST /upload_text
Content: "Tutorial on Docker containers and orchestration..."
```

**2. AI Extracts Concepts (Phase B)**
```python
# Backend automatically:
concepts = ["Docker", "Containers", "Images"]
confidence = 0.65  # Low confidence!

# Records the decision in database
ai_decisions.insert({
    "decision_type": "concept_extraction",
    "output_data": {"concepts": [...]},
    "confidence_score": 0.65,
    "validated": False,
    "created_at": datetime.utcnow()
})
```

**3. Low Confidence Triggers Dual-Pass (Phase C)**
```python
# AI critiques itself:
critique = {
    "issues_found": ["Missing key concepts", "Too generic"],
    "missing_concepts": ["Dockerfile", "docker-compose"],
    "incorrect_concepts": [],
    "confidence_adjustment": +0.07
}

# AI refines:
improved_concepts = ["Docker", "Containers", "Images",
                     "Dockerfile", "docker-compose"]
new_confidence = 0.72  # Better but still low
```

**4. Decision Appears in Validation Dashboard (Phase D)**

User visits: `http://localhost:3000/ai-validation`

Sees validation card:
```
📝 Validate Extracted Concepts

I extracted 5 concepts from this document, but I'm only 72% confident.
Can you help me verify?

Concepts: Docker, Containers, Images, Dockerfile, docker-compose

Are these concepts accurate?

[✅ Yes, these look correct]
[⚠️ Some are correct, some are wrong]
[❌ No, these are wrong]

Confidence: 72%
```

**5. User Validates or Corrects**

User clicks: **⚠️ "Some are correct, some are wrong"**

Edit form appears:
```
Corrected Concepts (comma-separated):
Docker, Containers, Dockerfile, docker-compose, Docker Hub, Orchestration

Optional: Why did you make this change?
"'Images' is too vague. Added 'Docker Hub' and 'Orchestration'
which are key concepts in this document."
```

**6. Feedback Recorded (Phase A)**
```python
user_feedback.insert({
    "ai_decision_id": 123,
    "feedback_type": "partial",
    "original_value": {"concepts": ["Docker", "Containers", "Images", ...]},
    "new_value": {"concepts": ["Docker", "Containers", "Dockerfile", ...]},
    "user_reasoning": "'Images' is too vague. Added 'Docker Hub'...",
    "processed": False,
    "created_at": datetime.utcnow()
})
```

**7. AI Learns and Improves**
```python
# System tracks:
- "Images" concept rejected as too vague
- User prefers specific terms like "Docker Hub"
- Future extractions will be more specific
- Confidence improves over time: 0.65 → 0.72 → 0.85 → 0.92
```

## The Agentic Loop

```
┌─────────────────────────────────────────────┐
│ 1. AI makes decision (concept extraction)   │
│    ↓ Records decision with confidence       │
│    ↓ confidence = 0.68 (LOW!)               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 2. AI questions itself (self-critique)      │
│    "Did I miss concepts? Are they too vague?"│
│    ↓ Critiques own work                     │
│    ↓ Refines → confidence = 0.72            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 3. Still low? Ask user (validation prompt)  │
│    Shows in /ai-validation dashboard        │
│    ↓ Generates user-friendly prompt         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 4. User validates/corrects                  │
│    Provides reasoning for changes           │
│    ↓ Submits feedback                       │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 5. System learns                            │
│    - Records correction in database         │
│    - Tracks accuracy trends                 │
│    - Adjusts future behavior                │
│    - Improves confidence calibration        │
└─────────────────────────────────────────────┘
                    ↓
         (Loop continues - AI gets smarter!)
```

## How to Access the System

### Frontend (User Interface)

**Validation Dashboard**
- URL: `http://localhost:3000/ai-validation`
- Features:
  - View low-confidence decisions needing validation
  - Validate/correct AI decisions
  - See accuracy metrics and improvement trends
  - Track pending validations by type

**Dashboard Widget**
- Real-time stats showing pending validations
- Accuracy metrics by confidence range
- Improvement trend indicators

### Backend API Endpoints

**Get Validation Prompts**
```bash
GET /feedback/validation-prompts?limit=10
Authorization: Bearer {token}

Response:
{
  "prompts": [...],
  "summary": {
    "total_pending": 5,
    "average_confidence": 0.68,
    "urgency_level": "medium",
    "by_type": {"concept_extraction": 5}
  },
  "count": 5
}
```

**Submit Feedback**
```bash
POST /feedback/submit
Authorization: Bearer {token}
Content-Type: application/json

{
  "decision_id": 123,
  "validation_result": "partial",  // "accepted", "rejected", "partial"
  "new_value": {
    "concepts": ["Docker", "Containers", "Dockerfile", "Docker Hub"]
  },
  "user_reasoning": "Images is too vague. Added Docker Hub."
}
```

**Get Accuracy Metrics**
```bash
GET /feedback/accuracy-metrics
Authorization: Bearer {token}

Response:
{
  "overall_accuracy": 0.78,
  "by_confidence_range": {
    "0-50%": {"accuracy": 0.45, "count": 10},
    "50-70%": {"accuracy": 0.62, "count": 25},
    "70-90%": {"accuracy": 0.81, "count": 40},
    "90%+": {"accuracy": 0.95, "count": 30}
  },
  "improvement_trend": 0.12,
  "total_decisions": 105,
  "validated_decisions": 58
}
```

**Get Low-Confidence Decisions**
```bash
GET /feedback/low-confidence-decisions?limit=20
Authorization: Bearer {token}

Returns: Array of AI decisions with confidence < 0.7
```

**Get Decision History**
```bash
GET /feedback/decisions/document/{document_id}
Authorization: Bearer {token}

Returns: All AI decisions for specific document
```

### Database Tables

**ai_decisions**
- Stores every AI decision with confidence scores
- Tracks validation status
- Links to documents and clusters

**user_feedback**
- Records all user corrections
- Includes user reasoning for improvements
- Tracks processing status for learning pipeline

## Configuration

### Environment Variables

```bash
# Enable/disable dual-pass extraction
ENABLE_DUAL_PASS=true

# Confidence threshold for dual-pass trigger
DUAL_PASS_THRESHOLD=0.75

# Minimum confidence to record concept
MIN_CONCEPT_CONFIDENCE=0.3
```

### Constants (backend/constants.py)

```python
# Dual-pass extraction settings
ENABLE_DUAL_PASS_EXTRACTION = True
DUAL_PASS_CONFIDENCE_THRESHOLD = 0.75

# Feedback thresholds
LOW_CONFIDENCE_THRESHOLD = 0.7  # Show in validation UI
HIGH_CONFIDENCE_THRESHOLD = 0.9  # Skip self-critique
```

## Testing the System

### 1. Upload a Test Document

Navigate to `http://localhost:3000/documents` and upload text with some ambiguity:

```
Example text:
"Docker is a platform for developing, shipping, and running applications
in containers. It uses images to package applications with dependencies.
Kubernetes orchestrates these containers in production."
```

### 2. Check Validation Dashboard

Visit `http://localhost:3000/ai-validation`

If the AI extracted concepts with < 75% confidence, you'll see a validation card.

### 3. Validate or Correct

- Click ✅ if AI is correct (teaches AI it was right)
- Click ⚠️ to make corrections (teaches AI how to improve)
- Click ❌ if completely wrong (teaches AI to avoid this pattern)

### 4. Track Improvement

Over time, check the accuracy metrics to see:
- Overall accuracy increasing
- Better confidence calibration
- Improvement trend going up

## Why It's Revolutionary

**Traditional AI:**
```
User: "Extract concepts from this document"
AI: "Here are the concepts: Docker, Containers, Images"
[No confidence, no learning, no improvement]
```

**Agentic AI:**
```
User: "Extract concepts from this document"
AI: "I extracted: Docker, Containers, Images (68% confident)"
AI: [Self-critique] "Wait, I might have missed 'Dockerfile'"
AI: "Updated: Docker, Containers, Images, Dockerfile (72% confident)"
AI: "Still uncertain - can you help validate this?"
User: "Images is too vague. Add Docker Hub, Orchestration"
AI: "Thanks! I learned: be more specific. Next time I'll do better."

[Next document...]
AI: "Docker, Containers, Dockerfile, Docker Hub, Orchestration (88% confident)"
```

## Key Benefits

1. **Transparency** - You always know how confident the AI is
2. **Self-awareness** - AI knows when to ask for help
3. **Continuous Learning** - Gets smarter with every correction
4. **User Control** - You validate and improve AI decisions
5. **Measurable Improvement** - Track accuracy metrics over time
6. **Efficient** - Only asks for help when genuinely uncertain

## Future Enhancements

Potential improvements:
- Automatic pattern detection from feedback
- Personalized learning per user
- Confidence calibration based on accuracy history
- A/B testing of different critique strategies
- Batch validation for similar decisions

## Support

For issues or questions:
- Check backend logs: `docker logs syncboard-backend`
- Check database: Query `ai_decisions` and `user_feedback` tables
- API docs: `http://localhost:8000/docs`

## Summary

The agentic learning system transforms SyncBoard from a static AI tool into a self-improving assistant that:
- Questions its own decisions
- Learns from mistakes
- Asks for help when uncertain
- Gets better over time

By validating AI decisions, you're not just correcting mistakes - you're teaching the AI to be smarter for everyone.
