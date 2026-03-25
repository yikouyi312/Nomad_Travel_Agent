from typing import Any, Dict, Optional
import json
import os
from datetime import datetime

from llm import call_llm_structured

# Verification results storage directory
VERIFICATION_DIR = os.path.join(os.path.dirname(__file__), "..", "verification_results")
os.makedirs(VERIFICATION_DIR, exist_ok=True)

VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid": {
            "type": "boolean",
            "description": "True if the itinerary strictly obeys all constraints.",
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of constraint violations (e.g. 'Flight returns on 15th but constraint is 14th')",
        },
        "final_message_to_user": {
            "type": "string",
            "description": "A nicely formatted Markdown response presenting the final validated itinerary, or explaining what went wrong if it couldn't be built.",
        },
    },
    "required": ["is_valid", "issues", "final_message_to_user"],
}


def verify_and_format_itinerary(
    draft_text: str, 
    constraints_json: str,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Acts as the Verifier layer. Reviews the text output from the Specialists against
    the strict JSON Constraint layer.
    
    Args:
        draft_text: Draft itinerary text from specialists
        constraints_json: JSON constraints for verification
        task_id: Optional task ID for saving verification results
    
    Returns:
        Verification result dict with is_valid, issues, final_message_to_user
    """

    system_prompt = """You are the Verifier for Nomad.
Your job is to cross-reference the proposed itinerary against the hard constraints.

HARD CONSTRAINTS:
{constraints_json}

If the itinerary violates any constraints (e.g. budget exceeded, dates wrong, wrong city),
set is_valid to false and list the issues.
If it is valid, format the draft into a beautiful Markdown response for the user."""

    messages = [
        {
            "role": "user",
            "content": f"Here is the draft itinerary to verify:\n\n{draft_text}",
        }
    ]

    result = call_llm_structured(
        messages=messages,
        schema=VERIFIER_SCHEMA,
        system=system_prompt.replace("{constraints_json}", constraints_json),
    )

    # Save verification result if task_id provided
    if task_id:
        _save_verification_result(task_id, result, draft_text, constraints_json)
    
    return result


def _save_verification_result(
    task_id: str,
    result: Dict[str, Any],
    draft_text: str,
    constraints_json: str,
) -> None:
    """
    Save verification result to file for later evaluation.
    
    Args:
        task_id: Task identifier
        result: Verification result from verify_and_format_itinerary
        draft_text: Original draft itinerary
        constraints_json: Constraints used for verification
    """
    verification_data = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "is_valid": result.get("is_valid"),
        "issues": result.get("issues", []),
        "final_message_to_user": result.get("final_message_to_user"),
        "draft_text": draft_text,
        "constraints": json.loads(constraints_json) if isinstance(constraints_json, str) else constraints_json,
    }
    
    # Save to task-specific file
    filename = f"{task_id}_verification.json"
    filepath = os.path.join(VERIFICATION_DIR, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(verification_data, f, indent=2, ensure_ascii=False)
        print(f"[Saved] Verification result -> {filepath}")
    except (IOError, json.JSONDecodeError) as e:
        print(f"⚠️ Failed to save verification result: {e}")


def load_verification_result(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a previously saved verification result by task_id.
    
    Args:
        task_id: Task identifier
    
    Returns:
        Verification result dict or None if not found
    """
    filename = f"{task_id}_verification.json"
    filepath = os.path.join(VERIFICATION_DIR, filename)
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None


def list_verification_results(limit: int = 20) -> list[Dict[str, Any]]:
    """
    List all saved verification results.
    
    Args:
        limit: Maximum number of results to return (sorted by timestamp descending)
    
    Returns:
        List of verification results
    """
    results = []
    
    if not os.path.isdir(VERIFICATION_DIR):
        return results
    
    for filename in os.listdir(VERIFICATION_DIR):
        if filename.endswith("_verification.json"):
            try:
                filepath = os.path.join(VERIFICATION_DIR, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append(data)
            except (IOError, json.JSONDecodeError):
                pass
    
    # Sort by timestamp descending
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results[:limit]
