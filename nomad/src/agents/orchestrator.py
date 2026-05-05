import json
from datetime import date
from typing import Any, Dict

from llm import call_llm_structured
from state import TravelState, TravelNeeds

# ============================================================================
# Global System Prompts
# ============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = f"""You are the Orchestrator for Nomad, an AI Travel Agent.
Today's date is {date.today().isoformat()}.
Your job is to read the user's message and:
1. Extract travel constraints (dates, budget, locations, preferences)
2. Determine what the user NEEDS (flight, hotel, activity)

When the user mentions dates without a year, assume the nearest FUTURE date.
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

HOTEL STAR RATING:
When the user mentions a hotel star rating, extract it as preferred_hotel_rating (integer 1-5).
Also decide hotel_rating_priority based on language strength:
- "hard": The user demands an exact rating or uses strong language ("must be", "need", "only", "exactly 4-star", "no less than")
- "soft": The user expresses a preference ("preferably", "ideally", "I'd like", "around", "at least X stars" without "must")
Examples:
- "Find a 3-star hotel" → preferred_hotel_rating=3, hotel_rating_priority="hard"
- "Must be at least 4 stars" → preferred_hotel_rating=4, hotel_rating_priority="hard"
- "Preferably 4-star" → preferred_hotel_rating=4, hotel_rating_priority="soft"
- "Hotel with at least 3 stars" → preferred_hotel_rating=3, hotel_rating_priority="hard"

NEEDS DETECTION (CRITICAL):
Determine what components the user needs. ALL default to FALSE.
Only set to true if the user EXPLICITLY requests or implies it:
- needs.flight = true: User mentions flying, flights, airport, airline, "fly to", round-trip, etc.
- needs.hotel = true: User mentions hotel, accommodation, stay, lodging, "book a room", etc.
- needs.activity = true: User mentions activities, restaurants, things to do, sightseeing, museums, dining,
  OR asks about a SPECIFIC PLACE (hours, prices, location, reviews) — we use search_places to answer these.
- When the user says "trip", "vacation", "travel to", "visit", "getaway", or similar general travel words,
  ALWAYS set activity=true in addition to flight/hotel, so we proactively suggest things to do.

Examples:
- "Find me a flight to Paris" -> flight=true, hotel=false, activity=false
- "Book a hotel in NYC" -> flight=false, hotel=true, activity=false
- "Plan a trip to Tokyo with flights and hotel" -> flight=true, hotel=true, activity=true
- "I want to travel to Rome next week" -> flight=true, hotel=true, activity=true
- "What restaurants should I visit in Rome?" -> flight=false, hotel=false, activity=true
- "What are the opening hours for the Louvre?" -> flight=false, hotel=false, activity=true
- "Plan a full trip to London" -> flight=true, hotel=true, activity=true

IMPORTANT: If needs.flight is true, we need origin, destination, start_date, end_date.
If any of these are missing, set them to null and ask the user in response_to_user.

DATE HANDLING when dates are missing:
If the user provides NO dates but needs flight or hotel:
- Ask if they have a general timeframe in mind
- Suggest 2-3 specific date ranges based on destination
- Keep the needs as detected, but note in response_to_user that dates are needed

If the user provides a VAGUE timeframe (e.g., "sometime in June", "a week next month", "over spring break"):
- Convert it to specific dates (pick the first available matching dates)
- Set those as start_date and end_date in updated_constraints
- Mention the dates you picked in response_to_user so the user can confirm or adjust
- Proceed with delegation normally

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
                "duration_days": {"type": "integer", "description": "Trip length in days (used when end_date is unclear)"},
                "budget_usd": {"type": "number"},
                "hotel_budget_per_night": {"type": "number", "description": "Max hotel cost per night in USD"},
                "num_travelers": {"type": "integer"},
                "dietary_needs": {"type": "array", "items": {"type": "string"}},
                "interests": {"type": "array", "items": {"type": "string"}},
                "preferred_hotel_rating": {"type": "integer", "description": "Desired hotel star rating (1-5)"},
                "hotel_rating_priority": {"type": "string", "enum": ["hard", "soft"], "description": "'hard' if user demands exact rating, 'soft' if it's a preference"},
                "hotel_location": {"type": "string", "description": "Specific neighborhood/area for the hotel, e.g. 'near Westminster', 'downtown', 'near Times Square'. Extract ONLY when user specifies a location preference for the hotel."},
            },
        },
        "needs": {
            "type": "object",
            "description": "What components the user EXPLICITLY needs. Default ALL to false.",
            "properties": {
                "flight": {"type": "boolean", "description": "True ONLY if user explicitly mentions flights/flying"},
                "hotel": {"type": "boolean", "description": "True ONLY if user explicitly mentions hotel/accommodation"},
                "activity": {"type": "boolean", "description": "True ONLY if user explicitly mentions activities/restaurants/sightseeing"},
            },
            "required": ["flight", "hotel", "activity"],
        },
        "response_to_user": {
            "type": "string",
            "description": "A brief natural language response to the user.",
        },
    },
    "required": ["intent", "updated_constraints", "needs", "response_to_user"],
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
            if "needs" in task_json:
                task_needs = task_json.get("needs")
                full_system += f"\n\nINITIAL NEEDS FROM TASK: {json.dumps(task_needs)}"
            # Backward compat: convert delegation to needs if present
            elif "delegation" in task_json:
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
        has_constraints = bool(task_json and task_json.get("updated_constraints"))
        
        # Determine needs from task_json
        task_needs = {"flight": False, "hotel": False, "activity": False}
        if task_json:
            if "needs" in task_json:
                task_needs = task_json["needs"]
            elif "delegation" in task_json:
                # Backward compat: convert delegation to needs
                d = task_json["delegation"]
                if d in ("logistics", "both"):
                    task_needs["flight"] = True
                    task_needs["hotel"] = True
                if d in ("activities", "both"):
                    task_needs["activity"] = True
        
        result = {
            "intent": "update_constraints" if has_constraints else "new_trip",
            "updated_constraints": task_json.get("updated_constraints", {}) if task_json else {},
            "needs": task_needs,
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
    
    # Re-compute end_date from start_date + duration_days
    # Fires when end_date is missing OR when duration_days was explicitly updated
    duration_changed = "duration_days" in updates and updates["duration_days"] is not None
    start_changed = "start_date" in updates and updates["start_date"] is not None
    if state.constraints.start_date and state.constraints.duration_days and (
        not state.constraints.end_date or duration_changed or start_changed
    ):
        from datetime import datetime, timedelta
        try:
            start = datetime.strptime(state.constraints.start_date, "%Y-%m-%d")
            end = start + timedelta(days=state.constraints.duration_days)
            state.constraints.end_date = end.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    # Update needs
    needs_data = analysis.get("needs", {})
    if needs_data:
        prior_needs = state.needs  # preserve before overwrite
        if isinstance(needs_data, dict):
            state.needs = TravelNeeds(**needs_data)
        elif isinstance(needs_data, TravelNeeds):
            state.needs = needs_data

        # On update_constraints: if date/location fields changed, re-enable
        # prior flight/hotel needs so the search runs again with new params.
        if analysis.get("intent") == "update_constraints":
            flight_hotel_fields = {"start_date", "end_date", "duration_days", "origin", "destination", "num_travelers"}
            changed_fields = set(k for k, v in updates.items() if v is not None)
            if changed_fields & flight_hotel_fields:
                if prior_needs.flight:
                    state.needs.flight = True
                if prior_needs.hotel:
                    state.needs.hotel = True
    
    # Backward compat: also set delegation_plan from needs
    if state.needs.flight or state.needs.hotel:
        if state.needs.activity:
            state.delegation_plan = "both"
        else:
            state.delegation_plan = "logistics"
    elif state.needs.activity:
        state.delegation_plan = "activities"
    else:
        state.delegation_plan = "none"
    
    return state



