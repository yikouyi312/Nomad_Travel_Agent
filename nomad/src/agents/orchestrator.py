import json
from typing import Any, Dict

from llm import call_llm_structured
from state import TravelState

# ============================================================================
# Global System Prompts
# ============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for Nomad, an AI Travel Agent. 
Your job is to read the user's message and extract travel constraints (dates, budget, locations, preferences).
Then you EITHER:
1. Create a NEW analysis from scratch if this is the first request
2. UPDATE the provided previous_result with new information from the user's message if one exists

CONSTRAINT UPDATE LOGIC:
- Extract ONLY fields that the user EXPLICITLY mentions or changes in their message
- For fields not mentioned, use null/empty to indicate "no change"
- This allows iteration: each new message increments the previous result
- Example: User says "Actually, I want to leave on the 15th" -> update "start_date" only

INTENT DETERMINATION:
- new_trip: Starting fresh travel planning
- update_constraints: Modifying existing constraints
- ask_question: Asking for guidance without providing new constraints
- confirm_itinerary: Confirming/finalizing the plan

DELEGATION:
- logistics: origin, destination, dates, or budget mentioned
- activities: interests or dietary needs mentioned
- both: both logistics AND activity preferences mentioned
- none: no actionable constraints provided

CONFLICT HANDLING:
If new information contradicts previous constraints, WARN the user explicitly.
Example: "Note: You mentioned Rome for destination, but previously said Paris. Updating to Rome."
"""

# ============================================================================
# Schema Definition
# ============================================================================

ORCHESTRATOR_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["new_trip", "update_constraints", "ask_question", "confirm_itinerary"],
            "description": "What the user is trying to do.",
        },
        "updated_constraints": {
            "type": "object",
            "description": "The new or updated constraints extracted from the users message.",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "budget_usd": {"type": "number"},
                "num_travelers": {"type": "integer"},
                "dietary_needs": {"type": "array", "items": {"type": "string"}},
                "interests": {"type": "array", "items": {"type": "string"}},
            },
        },
        "delegation": {
            "type": "string",
            "enum": ["logistics", "activities", "both", "none"],
            "description": "Which specialist needs to run based on these new constraints.",
        },
        "response_to_user": {
            "type": "string",
            "description": "A brief natural language response to the user.",
        },
    },
    "required": ["intent", "updated_constraints", "delegation", "response_to_user"],
}

# ============================================================================
# Main API Functions
# ============================================================================



def analyze_user_input(user_msg: str, state: TravelState) -> Dict[str, Any]:
    """
    Step 1: The Orchestrator reads the user message and the current state,
    then outputs structured JSON containing updated constraints and a delegation plan.
    """

    messages = state.messages + [{"role": "user", "content": user_msg}]

    # We append the current constraints to the system prompt
    full_system = ORCHESTRATOR_SYSTEM_PROMPT + "\n\n" + state.get_context_string()

    result = call_llm_structured(
        messages=messages, schema=ORCHESTRATOR_ANALYSIS_SCHEMA, system=full_system
    )

    return result

def analyze_user_input(
    user_msg: str, state: TravelState, task_json: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Unified input processing: 
    - task_json: Extract schema fields directly (no LLM)
    - user_msg: Process with ORCHESTRATOR_SYSTEM_PROMPT (handles JSON or natural language)
    
    If both provided: task_json result becomes previous_result in context for LLM.
    
    Args:
        user_msg: User message (can be natural language or JSON format)
        state: Current TravelState with message history and context
        task_json: Optional structured task input
    
    Returns:
        Dict matching ORCHESTRATOR_ANALYSIS_SCHEMA
    """
    
    # Step 1: Extract schema fields from task_json (direct extraction, no LLM)
    state = update_state_from_analysis(state, task_json) if task_json else state

    # Step 2: Process user_msg with ORCHESTRATOR_SYSTEM_PROMPT
    if user_msg and user_msg.strip():
        context_str = state.get_context_string()
        # Add initial_result from task_json as previous_result for LLM context
        messages = state.messages + [{"role": "user", "content": user_msg}]
        full_system = ORCHESTRATOR_SYSTEM_PROMPT + "\n\n" + context_str
        
        result = call_llm_structured(
            messages=messages,
            schema=ORCHESTRATOR_ANALYSIS_SCHEMA,
            system=full_system,
        )
        
        # Merge initial_result (from task_json) with LLM result
        # LLM result takes priority, but we preserve initial_result fields not mentioned by user
        return result
    else:
        # If no user_msg, return result based on task_json extraction only
        return {
            "intent": "new_trip" if not task_json else "update_constraints",
            "updated_constraints": task_json.get("updated_constraints", {}) if task_json else {},
            "delegation": "none",
            "response_to_user": "",
        }
    


def update_state_from_analysis(
    state: TravelState, analysis: Dict[str, Any]
) -> TravelState:
    """
    Applies the extracted constraints from orchestrator analysis to the TravelState.
    
    Args:
        state: Current TravelState
        analysis: Result from analyze_user_input()
    
    Returns:
        Updated TravelState
    """
    updates = analysis.get("updated_constraints", {})
    
    for key, value in updates.items():
        if value is not None and hasattr(state.constraints, key):
            current_val = getattr(state.constraints, key)
            
            # For lists: merge unique items
            if isinstance(current_val, list) and isinstance(value, list):
                new_list = list(set(current_val + value))
                setattr(state.constraints, key, new_list)
            # For other types: overwrite
            else:
                setattr(state.constraints, key, value)
    
    # Update delegation plan if provided
    delegation = analysis.get("delegation", "none")
    if delegation != "none":
        state.delegation_plan = delegation
    return state



