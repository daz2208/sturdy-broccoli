"""
Validation Prompt System for Agentic Learning (Phase C).

Generates user-friendly validation prompts for low-confidence AI decisions.
Helps users validate and correct AI decisions in natural language.
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def generate_validation_prompt(decision_type: str, output_data: Dict, confidence_score: float) -> Dict[str, Any]:
    """
    Generate a user-friendly validation prompt for a low-confidence decision.

    Args:
        decision_type: Type of AI decision (concept_extraction, clustering, etc.)
        output_data: The AI's output that needs validation
        confidence_score: How confident the AI is (0.0-1.0)

    Returns:
        {
            "title": "Validate Document Clustering",
            "message": "I placed this document in the 'DevOps' cluster, but I'm only 62% confident...",
            "question": "Is this correct?",
            "options": ["Yes, correct", "No, change it", "Not sure"],
            "decision_data": {...}  # Original decision data
        }
    """
    if decision_type == "concept_extraction":
        return _prompt_concept_extraction(output_data, confidence_score)
    elif decision_type == "clustering":
        return _prompt_clustering(output_data, confidence_score)
    else:
        return _prompt_generic(decision_type, output_data, confidence_score)


def _prompt_concept_extraction(output_data: Dict, confidence: float) -> Dict:
    """Generate prompt for concept extraction validation."""
    concepts = output_data.get("concepts", [])
    concept_names = [c.get("name") for c in concepts if isinstance(c, dict)]

    confidence_pct = int(confidence * 100)

    return {
        "title": "📝 Validate Extracted Concepts",
        "message": (
            f"I extracted {len(concepts)} concepts from this document, "
            f"but I'm only {confidence_pct}% confident. "
            "Can you help me verify?"
        ),
        "concepts": concept_names,
        "question": "Are these concepts accurate?",
        "options": [
            {
                "value": "correct",
                "label": "✅ Yes, these look correct",
                "feedback_type": "accepted"
            },
            {
                "value": "partial",
                "label": "⚠️ Some are correct, some are wrong",
                "feedback_type": "partial",
                "requires_edit": True
            },
            {
                "value": "incorrect",
                "label": "❌ No, these are wrong",
                "feedback_type": "rejected",
                "requires_edit": True
            }
        ],
        "confidence": confidence,
        "decision_type": "concept_extraction"
    }


def _prompt_clustering(output_data: Dict, confidence: float) -> Dict:
    """Generate prompt for clustering validation."""
    cluster_name = output_data.get("cluster_name", "Unknown")
    cluster_id = output_data.get("cluster_id")

    confidence_pct = int(confidence * 100)

    return {
        "title": f"🗂️ Validate Cluster Assignment",
        "message": (
            f"I placed this document in the '{cluster_name}' cluster "
            f"(ID: {cluster_id}), but I'm only {confidence_pct}% confident. "
            "Does this cluster make sense?"
        ),
        "cluster": {
            "id": cluster_id,
            "name": cluster_name
        },
        "question": "Is this the right cluster?",
        "options": [
            {
                "value": "correct",
                "label": f"✅ Yes, '{cluster_name}' is correct",
                "feedback_type": "accepted"
            },
            {
                "value": "move",
                "label": "🔄 No, move to different cluster",
                "feedback_type": "move_cluster",
                "requires_action": True
            },
            {
                "value": "new",
                "label": "➕ Create new cluster for this",
                "feedback_type": "create_cluster",
                "requires_action": True
            }
        ],
        "confidence": confidence,
        "decision_type": "clustering"
    }


def _prompt_generic(decision_type: str, output_data: Dict, confidence: float) -> Dict:
    """Generate generic validation prompt."""
    confidence_pct = int(confidence * 100)

    return {
        "title": f"🤔 Validate {decision_type.replace('_', ' ').title()}",
        "message": (
            f"I made a {decision_type.replace('_', ' ')} decision, "
            f"but I'm only {confidence_pct}% confident. "
            "Can you verify this is correct?"
        ),
        "question": "Is this decision accurate?",
        "options": [
            {
                "value": "correct",
                "label": "✅ Yes, correct",
                "feedback_type": "accepted"
            },
            {
                "value": "incorrect",
                "label": "❌ No, incorrect",
                "feedback_type": "rejected"
            }
        ],
        "confidence": confidence,
        "decision_type": decision_type,
        "output_data": output_data
    }


def format_validation_summary(validations: List[Dict]) -> Dict[str, Any]:
    """
    Format a list of pending validations into a user-friendly summary.

    Args:
        validations: List of validation prompts

    Returns:
        {
            "total": 5,
            "by_type": {"concept_extraction": 3, "clustering": 2},
            "avg_confidence": 0.65,
            "urgency": "medium",  # low, medium, high
            "message": "You have 5 pending validations that could improve AI accuracy"
        }
    """
    if not validations:
        return {
            "total": 0,
            "by_type": {},
            "avg_confidence": 1.0,
            "urgency": "none",
            "message": "No pending validations! The AI is performing well."
        }

    total = len(validations)
    by_type = {}
    confidences = []

    for v in validations:
        decision_type = v.get("decision_type", "unknown")
        by_type[decision_type] = by_type.get(decision_type, 0) + 1

        confidence = v.get("confidence", 0.5)
        confidences.append(confidence)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    # Determine urgency
    if avg_confidence < 0.5:
        urgency = "high"
        urgency_message = "Several low-confidence decisions need your attention!"
    elif avg_confidence < 0.65:
        urgency = "medium"
        urgency_message = "Some decisions could use your validation."
    else:
        urgency = "low"
        urgency_message = "A few decisions would benefit from your review."

    return {
        "total": total,
        "by_type": by_type,
        "avg_confidence": round(avg_confidence, 2),
        "urgency": urgency,
        "message": f"You have {total} pending validations. {urgency_message}"
    }
