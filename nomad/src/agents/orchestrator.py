from typing import Any, Dict

from src.llm import call_llm_structured
from src.state import TravelState

# Schema for the Orchestrator's structured output when analyzing user input
ORCHESTRATOR_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "new_trip",
                "update_constraints",
                "ask_question",
                "confirm_itinerary",
            ],
            "description": "What the user is trying to do.",
        },
        "updated_constraints": {
            "type": "object",
            "description": "The new or updated constraints extracted from the user's message. Only include fields that the user explicitly mentioned.",
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
            "description": "A brief natural language response to the user. E.g. 'I will start looking for flights...'",
        },
    },
    "required": ["intent", "updated_constraints", "delegation", "response_to_user"],
}


def analyze_user_input(user_msg: str, state: TravelState) -> Dict[str, Any]:
    """
    Step 1: The Orchestrator reads the user message and the current state,
    then outputs structured JSON containing updated constraints and a delegation plan.
    """

    system_prompt = """You are the Orchestrator for Nomad, an AI Travel Agent. 
Your job is to read the user's message, extract any travel constraints (dates, budget, locations, preferences), 
and update the Constraint Layer. 

If the user changes a constraint (e.g. "Actually I want to leave on the 15th"), update it.
If the user provides enough info to start searching (origin, destination, dates), delegate to 'logistics' or 'both'.
If they just ask a general question, delegate to 'none'."""

    messages = state.messages + [{"role": "user", "content": user_msg}]

    # We append the current constraints to the system prompt
    full_system = system_prompt + "\n\n" + state.get_context_string()

    result = call_llm_structured(
        messages=messages, schema=ORCHESTRATOR_ANALYSIS_SCHEMA, system=full_system
    )

    return result


def update_state_from_analysis(
    state: TravelState, analysis: Dict[str, Any]
) -> TravelState:
    """Applies the Orchestrator's extracted constraints to our Pydantic state."""
    updates = analysis.get("updated_constraints", {})

    # Iterate over the dict to update the Pydantic model
    for key, value in updates.items():
        if value is not None and hasattr(state.constraints, key):
            # For lists, we might want to append rather than overwrite,
            # but for simplicity let's overwrite or append based on type
            current_val = getattr(state.constraints, key)
            if isinstance(current_val, list) and isinstance(value, list):
                # Only add new unique items
                new_list = list(set(current_val + value))
                setattr(state.constraints, key, new_list)
            else:
                setattr(state.constraints, key, value)

    return state
