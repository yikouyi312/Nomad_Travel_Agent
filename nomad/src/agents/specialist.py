from typing import Any, Dict, List, Tuple
import json
import os
from datetime import datetime

from config import MAX_AGENT_TURNS
from llm import call_llm, extract_text
from tools.dispatch import create_tool_result_message, dispatch_tool
from tools.schemas import ACTIVITIES_TOOLS, LOGISTICS_TOOLS

# Candidates storage directory
CANDIDATES_DIR = os.path.join(os.path.dirname(__file__), "..", "search_candidates")
os.makedirs(CANDIDATES_DIR, exist_ok=True)


def _categorize_search_result(tool_name: str, result: Any) -> str:
    """
    Categorize search result by tool name.
    
    Args:
        tool_name: Name of the tool that was called
        result: Result from the tool
    
    Returns:
        Category: 'flights', 'hotels', 'activities', or 'unknown'
    """
    tool_lower = tool_name.lower()
    
    if 'flight' in tool_lower or 'search_flights' in tool_lower:
        return 'flights'
    elif 'hotel' in tool_lower or 'search_hotels' in tool_lower:
        return 'hotels'
    elif 'activity' in tool_lower or 'restaurant' in tool_lower or 'search_activities' in tool_lower:
        return 'activities'
    else:
        return 'unknown'


def _save_search_candidate(
    task_id: str,
    category: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Any,
) -> None:
    """
    Save search result as candidate for later retrieval.
    
    Args:
        task_id: Task identifier
        category: 'flights', 'hotels', or 'activities'
        tool_name: Name of tool that was called
        tool_input: Input parameters to the tool
        tool_result: Result from the tool
    """
    candidate = {
        "task_id": task_id,
        "category": category,
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_result": tool_result,
    }
    
    # Save to category-specific file
    candidates_dir = os.path.join(CANDIDATES_DIR, task_id)
    os.makedirs(candidates_dir, exist_ok=True)
    
    # Append to category file
    category_file = os.path.join(candidates_dir, f"{category}_candidates.json")
    
    try:
        # Read existing candidates if file exists
        candidates_list = []
        if os.path.exists(category_file):
            with open(category_file, "r", encoding="utf-8") as f:
                candidates_list = json.load(f)
        
        # Append new candidate
        candidates_list.append(candidate)
        
        # Save back
        with open(category_file, "w", encoding="utf-8") as f:
            json.dump(candidates_list, f, indent=2, ensure_ascii=False)
        
        print(f"[Saved] Candidate -> {category_file} ({len(candidates_list)} total)")
    except (IOError, json.JSONDecodeError) as e:
        print(f"⚠️ Failed to save search candidate: {e}")


def run_specialist(
    task_description: str, 
    tools: List[Dict[str, Any]], 
    constraints_json: str,
    task_id: str = None
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    The canonical ReAct tool-calling loop.
    Executes tools until it reaches a final answer or max turns.
    
    Args:
        task_description: Description of the task
        tools: List of available tools
        constraints_json: Constraints for the task
        task_id: Optional task ID for cache tracking (used for benchmark snapshots)
    
    Returns:
        Tuple of (draft_text, search_results_dict, verifier_context) where:
          - draft_text: Final itinerary text
          - search_results_dict: {"flights": [...], "hotels": [...], "activities": [...]}
          - verifier_context: Dict with specialist reasoning and recommendations for verifier:
            {
              "specialist_reasoning": "Why these options were chosen",
              "search_coverage": {"flights": count, "hotels": count, "activities": count},
              "key_decisions": ["Decision 1", "Decision 2"],
              "budget_analysis": "Budget usage analysis",
              "risk_factors": ["Any concerns"],
              "recommendations": "Overall recommendation for verifier"
            }
    """

    system_prompt = f"""You are a specialized Nomad Sub-Agent.
Your task: {task_description}

You must adhere strictly to these constraints:
{constraints_json}

YOUR JOB - THREE PHASES:

PHASE 1: SEARCH
- Search for multiple options in each category
- Collect 5+ flights, 5+ hotels, 10+ activities

PHASE 2: FILTER & RANK (IMPORTANT!)
- For FLIGHTS: Rank and present top 3-5:
  * Best price (cheapest option)
  * Best timing (most convenient times)
  * Best comfort (best airlines/amenities)
- For HOTELS: Rank and present top 3-5:
  * Best price (cheapest per night)
  * Best rating (highest rated)
  * Best value (good balance of price and rating)
- For ACTIVITIES: Present top 5-8 across different:
  * Time slots (morning/afternoon/evening options)
  * Price ranges (budget/mid/premium)
  * Types (attractions/dining/museums etc)

PHASE 3: SUMMARIZE
- Present the TOP candidates ONLY with full details
- Include ranking criteria you used (e.g. "Best price: $X", "Best comfort: 5-star airline")
- Verifier will choose final selections from these top options

IMPORTANT CONSTRAINTS:
- Never violate date or hard budget limits
- Top candidates must all meet basic constraints
- Show WHY each candidate is in the "top" list

Return a summary of the TOP candidates with their rankings and details."""

    messages = [
        {
            "role": "user",
            "content": "Search, filter for top candidates, and present them with ranking criteria.",
        }
    ]

    # Track search results by category
    search_results = {
        "flights": [],
        "hotels": [],
        "activities": [],
    }
    
    # Track specialist analysis
    verifier_context = {
        "specialist_reasoning": [],
        "search_coverage": {"flights": 0, "hotels": 0, "activities": 0},
        "key_decisions": [],
        "budget_analysis": "",
        "risk_factors": [],
        "recommendations": "",
        "tool_calls_summary": [],  # Track what tools were called
    }

    turn = 0
    while turn < MAX_AGENT_TURNS:
        print(f"  [Specialist Turn {turn + 1}] Thinking...")

        response = call_llm(messages=messages, system=system_prompt, tools=tools)

        stop_reason = response.get("stop_reason")
        content_blocks = response.get("content", [])
        
        # Extract any thinking/reasoning from assistant response
        for block in content_blocks:
            if block.get("type") == "text":
                reasoning = block.get("text", "").strip()
                if reasoning:
                    verifier_context["specialist_reasoning"].append(reasoning)
        
        # Append assistant response (which might contain tool_uses and text)
        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason != "tool_use":
            # We are done! Build verifier context and return
            draft_text = extract_text(response)
            
            # Finalize verifier context
            verifier_context["final_draft"] = draft_text
            verifier_context["total_searches"] = sum(verifier_context["search_coverage"].values())
            
            return draft_text, search_results, verifier_context

        # We need to execute tools
        tool_results = []
        for block in content_blocks:
            if block["type"] == "tool_use":
                tool_use_id = block["id"]
                tool_name = block["name"]
                tool_args = block["input"].copy()
                
                # Add task_id and turn to tool arguments for snapshot caching
                if task_id:
                    tool_args["task_id"] = task_id
                tool_args["turn"] = turn

                result, candidate_number = dispatch_tool(tool_name, tool_args)
                
                # Save search result as candidate
                category = _categorize_search_result(tool_name, result)
                
                # ✨ FIX: Extract actual search results from nested dict and add to flat list
                if category != 'unknown' and result and not result.get("error"):
                    if category == "flights":
                        # Flights results are in "best_flights" and "other_flights"
                        flights_list = result.get("best_flights", []) + result.get("other_flights", [])
                        search_results["flights"].extend(flights_list)
                    elif category == "hotels":
                        # Hotels results are in "properties"
                        hotels_list = result.get("properties", [])
                        search_results["hotels"].extend(hotels_list)
                    elif category == "activities":
                        # Activities results are in "local_results"
                        activities_list = result.get("local_results", [])
                        search_results["activities"].extend(activities_list)
                
                if task_id:
                    _save_search_candidate(task_id, category, tool_name, block["input"], result)
                    
                    # Accumulate search results by category for final output
                    verifier_context["search_coverage"][category] += candidate_number
                    # Track tool call
                    verifier_context["tool_calls_summary"].append({
                        "tool": tool_name,
                        "category": category,
                        "result_count": candidate_number,
                        "turn": turn + 1,
                    })
                
                tool_results.append(
                    create_tool_result_message(tool_use_id, tool_name, result)
                )

        # Append tool results as a user message
        messages.append({"role": "user", "content": tool_results})

        turn += 1

    return "Error: Specialist reached maximum tool turns without a final answer.", search_results, {
        **verifier_context,
        "error": "Max turns reached",
    }


def run_logistics_specialist(constraints_json: str, task_id: str = None) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Specialist for finding flights and hotels.
    
    Returns:
        Tuple of (draft_text, search_results, verifier_context) where:
          - draft_text: Final itinerary text
          - search_results: {"flights": [...], "hotels": [...], "activities": [...]}
          - verifier_context: Specialist analysis for verifier stage
    """
    return run_specialist(
        task_description="Find the best flights and hotels for the trip.",
        tools=LOGISTICS_TOOLS,
        constraints_json=constraints_json,
        task_id=task_id,
    )


def run_activities_specialist(constraints_json: str, task_id: str = None) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Specialist for finding restaurants and things to do.
    
    Returns:
        Tuple of (draft_text, search_results, verifier_context) where:
          - draft_text: Final itinerary text
          - search_results: {"flights": [...], "hotels": [...], "activities": [...]}
          - verifier_context: Specialist analysis for verifier stage
    """
    return run_specialist(
        task_description="Find restaurants (matching dietary needs) and activities (matching interests).",
        tools=ACTIVITIES_TOOLS,
        constraints_json=constraints_json,
        task_id=task_id,
    )


def retrieve_candidates(task_id: str, category: str = None) -> Dict[str, Any]:
    """
    Retrieve saved search candidates for a task.
    
    Args:
        task_id: Task identifier
        category: Optional category filter ('flights', 'hotels', 'activities')
                 If None, returns all categories
    
    Returns:
        Dict with candidates: {category: [candidate1, candidate2, ...]}
    """
    result = {}
    candidates_dir = os.path.join(CANDIDATES_DIR, task_id)
    
    if not os.path.isdir(candidates_dir):
        return result
    
    categories = [category] if category else ["flights", "hotels", "activities"]
    
    for cat in categories:
        category_file = os.path.join(candidates_dir, f"{cat}_candidates.json")
        if os.path.exists(category_file):
            try:
                with open(category_file, "r", encoding="utf-8") as f:
                    candidates = json.load(f)
                    result[cat] = candidates
            except (IOError, json.JSONDecodeError):
                result[cat] = []
    
    return result


def list_candidate_tasks() -> List[str]:
    """
    List all task IDs that have saved candidates.
    
    Returns:
        List of task_ids
    """
    if not os.path.isdir(CANDIDATES_DIR):
        return []
    
    return [d for d in os.listdir(CANDIDATES_DIR) 
            if os.path.isdir(os.path.join(CANDIDATES_DIR, d))]
