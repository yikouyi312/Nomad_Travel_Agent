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



def analyze_user_input(
    user_msg: str, state: TravelState, task_json: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Unified input processing: 
    - task_json: Extract schema fields directly (no LLM)
    - user_msg: Process with ORCHESTRATOR_SYSTEM_PROMPT (handles JSON or natural language)
    - Both: Merge task_json constraints into LLM context for combined analysis
    
    Args:
        user_msg: User message (can be natural language or JSON format)
        state: Current TravelState with message history and context
        task_json: Optional structured task input (can include task_id and updated_constraints)
    
    Returns:
        Analysis result (Dict matching ORCHESTRATOR_ANALYSIS_SCHEMA)
    """
    
    # Step 1: Extract task_id from task_json if provided
    if task_json and "task_id" in task_json:
        state.task_id = task_json["task_id"]
    
    # Step 1b: If user_msg is empty, try to extract from task_json.input.content
    if (not user_msg or not user_msg.strip()) and task_json:
        input_data = task_json.get("input", {})
        if isinstance(input_data, dict) and input_data.get("content"):
            user_msg = input_data["content"] if isinstance(input_data["content"], str) else json.dumps(input_data["content"])
    
    # Step 2: Process user_msg with ORCHESTRATOR_SYSTEM_PROMPT
    if user_msg and user_msg.strip():
        MAX_CONTEXT_CHARS = 8000
        context_str = state.get_context_string()
        if len(context_str) > MAX_CONTEXT_CHARS:
            context_str = context_str[-MAX_CONTEXT_CHARS:]
        messages = state.messages + [{"role": "user", "content": user_msg}]
        
        # Build system prompt with task_json context if provided
        full_system = ORCHESTRATOR_SYSTEM_PROMPT + "\n\n" + context_str
        
        # If both task_json and user_msg provided, add task_json data to context
        if task_json:
            if "updated_constraints" in task_json:
                task_constraints = task_json.get("updated_constraints", {})
                full_system += f"\n\nINITIAL CONSTRAINTS FROM TASK:\n{json.dumps(task_constraints, indent=2)}"
            if "delegation" in task_json:
                task_delegation = task_json.get("delegation")
                full_system += f"\n\nINITIAL DELEGATION FROM TASK: {task_delegation}"
        
        result = call_llm_structured(
            messages=messages,
            schema=ORCHESTRATOR_ANALYSIS_SCHEMA,
            system=full_system,
        )
        
        return result
    else:
        # If no user_msg, return result based on task_json extraction only
        task_delegation = "none"
        if task_json and "delegation" in task_json:
            task_delegation = task_json["delegation"]
        
        has_constraints = bool(task_json and task_json.get("updated_constraints"))
        
        result = {
            "intent": "update_constraints" if has_constraints else "new_trip",
            "updated_constraints": task_json.get("updated_constraints", {}) if task_json else {},
            "delegation": task_delegation,
            "response_to_user": "",
        }
        return result
    


def update_state_from_analysis(
    state: TravelState, analysis: Dict[str, Any]
) -> TravelState:
    """
    Applies the extracted constraints from orchestrator analysis to the TravelState.
    Also updates task_id if provided in the analysis.
    
    Args:
        state: Current TravelState
        analysis: Result from task_json or analyze_user_input()
    
    Returns:
        Updated TravelState
    """
    
    # Update constraints
    updates = analysis.get("updated_constraints", {})
    
    for key, value in updates.items():
        if value is not None and hasattr(state.constraints, key):
            current_val = getattr(state.constraints, key)
            
            # For lists: merge unique items
            if isinstance(current_val, list) and isinstance(value, list):
                if value and set(value).isdisjoint(set(current_val)):
                    setattr(state.constraints, key, value)
                else:
                    new_list = list(dict.fromkeys(current_val + value))
                    setattr(state.constraints, key, new_list)
            else:
                # Scalar types: overwrite
                setattr(state.constraints, key, value)
    
    # Update delegation plan if provided
    delegation = analysis.get("delegation", "none")
    if delegation != "none":
        state.delegation_plan = delegation
    return state



