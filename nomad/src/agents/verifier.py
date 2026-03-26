from typing import Any, Dict, Optional
import json
import os
from datetime import datetime

from llm import call_llm_structured
from config import VERIFICATION_DIR

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
            "description": "List of constraint violations",
        },
        "itinerary": {
            "type": "object",
            "description": "Complete itinerary with available components. Only include sections that have data — omit flights if none booked, omit hotels if not needed, etc.",
            "properties": {
                "flights": {
                    "type": "object",
                    "description": "Flight details (omit entirely if no flights in this trip)",
                    "properties": {
                        "outbound": {
                            "type": "object",
                            "description": "Complete outbound flight details (all fields from search results)"
                        },
                        "return": {
                            "type": "object",
                            "description": "Complete return flight details (all fields from search results)"
                        }
                    }
                },
                "hotels": {
                    "type": "object",
                    "description": "Hotel details with check-in/check-out dates (omit if not needed)"
                },
                "activities": {
                    "type": "array",
                    "description": "List of activities with full details including date and time (omit if none)",
                    "items": {
                        "type": "object",
                        "description": "Complete activity/restaurant details with date"
                    }
                },
                "estimated_cost": {"type": "number", "description": "Total estimated cost in USD for booked components only"},
            }
        },
        "final_message_to_user": {
            "type": "string",
            "description": "Concise summary or error explanation",
        },
    },
    "required": ["is_valid", "issues", "itinerary", "final_message_to_user"],
}


def verify_and_format_itinerary(
    draft_text: str, 
    constraints_json: str,
    task_id: Optional[str] = None,
    search_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Acts as the Verifier layer. Reviews the text output from the Specialists against
    the strict JSON Constraint layer.
    
    Returns COMPLETE ITINERARY with all details (flights, hotels, activities).
    
    Args:
        draft_text: Draft itinerary text from specialists
        constraints_json: JSON constraints for verification
        task_id: Optional task ID for saving verification results
        search_results: Optional dict with search results (for reference only, verifier returns full details)
    
    Returns:
        Verification result dict with:
          - is_valid: boolean
          - issues: list of violations
          - itinerary: COMPLETE itinerary with all details (flights, hotels, activities)
          - final_message_to_user: concise summary
    """

    # Build candidate information for the prompt
    available_candidates = "TOP CANDIDATES (Pre-filtered by Specialist):\n"
    
    if search_results:
        if search_results.get("flights"):
            available_candidates += f"\n✈️  FLIGHTS ({len(search_results['flights'])} options):\n"
            for i, flight in enumerate(search_results["flights"]):
                available_candidates += f"  [{i}] {flight}\n"
        
        if search_results.get("hotels"):
            available_candidates += f"\n🏨 HOTELS ({len(search_results['hotels'])} options):\n"
            for i, hotel in enumerate(search_results["hotels"]):
                available_candidates += f"  [{i}] {hotel}\n"
        
        if search_results.get("activities"):
            available_candidates += f"\n🎯 ACTIVITIES ({len(search_results['activities'])} options):\n"
            for i, activity in enumerate(search_results["activities"]):
                available_candidates += f"  [{i}] {activity}\n"
    else:
        available_candidates += "No candidates provided. Work from the draft text."

    # Build adaptive selection criteria based on what's available
    selection_lines = []
    if search_results and search_results.get("flights"):
        selection_lines.append("- Outbound Flight: Balance of price vs convenience")
        selection_lines.append("- Return Flight: Align with hotel checkout and trip activities")
    if search_results and search_results.get("hotels"):
        selection_lines.append("- Hotel: Best value (meets amenities AND price within remainder of budget)")
    if search_results and search_results.get("activities"):
        selection_lines.append("- Activities: Spread across trip days, match interests and budget")
    selection_criteria = "\n".join(selection_lines) if selection_lines else "- Select the best options from the draft."

    # Describe which components are expected
    components = []
    if search_results:
        if search_results.get("flights"):
            components.append("flights")
        if search_results.get("hotels"):
            components.append("hotels/accommodation")
        if search_results.get("activities"):
            components.append("activities/restaurants")
    component_note = ", ".join(components) if components else "all available"

    system_prompt = f"""You are the Verifier for Nomad.
Your job is to cross-reference the proposed itinerary against the hard constraints.

HARD CONSTRAINTS:
{constraints_json}

TOP CANDIDATES PROVIDED BY SPECIALIST:
{available_candidates}

COMPONENTS IN THIS TRIP: {component_note}
NOTE: Not every trip requires flights. If no flights are provided, the trip is local or the user only needs hotels/activities. Build the itinerary with whatever components are available.

SELECTION CRITERIA:
{selection_criteria}

OUTPUT REQUIREMENTS:
- is_valid: true if all constraints met after your selection
- issues: any violations found
- itinerary: Complete confirmed trip with ONLY the relevant components ({component_note}). Omit sections with no data (e.g. skip "flights" if none provided).
- estimated_cost: Total cost for only the booked components
- final_message_to_user: Friendly summary of passenger's confirmed trip"""
    
    messages = [
        {
            "role": "user",
            "content": f"Here is the draft itinerary with search results:\n\n{draft_text}",
        }
    ]

    result = call_llm_structured(
        messages=messages,
        schema=VERIFIER_SCHEMA,
        system=system_prompt
    )

    # Save verification result if task_id provided
    if task_id:
        _save_verification_result(task_id, result, draft_text, constraints_json, search_results)
    
    return result


def _save_verification_result(
    task_id: str,
    result: Dict[str, Any],
    draft_text: str,
    constraints_json: str,
    search_results: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save verification result to file for later evaluation.
    
    Args:
        task_id: Task identifier
        result: Verification result from verify_and_format_itinerary
        draft_text: Original draft itinerary
        constraints_json: Constraints used for verification
        search_results: Optional search results (not required for detail expansion anymore)
    """
    verification_data = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "is_valid": result.get("is_valid"),
        "issues": result.get("issues", []),
        "itinerary": result.get("itinerary"),  # Complete itinerary with all details
        "final_message_to_user": result.get("final_message_to_user"),
        "draft_text": draft_text,
        "constraints": json.loads(constraints_json) if isinstance(constraints_json, str) else constraints_json,
    }
    
    # Include search results if provided for reference/analytics
    if search_results:
        verification_data["search_results"] = search_results
    
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


def determine_details(
    blueprint: Dict[str, Any],
    search_results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Expand itinerary blueprint with detailed information from search results.
    Call this function ONLY when you need full details to reduce token usage.
    
    Args:
        blueprint: itinerary_blueprint from verify_and_format_itinerary()
        search_results: Dict containing search result lists
            {
              "flights": [...], 
              "hotels": [...], 
              "activities": [...]
            }
    
    Returns:
        Expanded itinerary with full details
    """
    detailed = {
        "flights": {},
        "hotels": {},
        "activities": [],
        "cost_breakdown": {},
    }
    
    # Expand flights
    outbound_ref = blueprint.get("flights", {}).get("outbound_ref")
    if outbound_ref and "flights" in search_results:
        idx = int(outbound_ref.split("_")[1])
        if idx < len(search_results["flights"]):
            detailed["flights"]["outbound"] = search_results["flights"][idx]
    
    return_ref = blueprint.get("flights", {}).get("return_ref")
    if return_ref and "flights" in search_results:
        idx = int(return_ref.split("_")[1])
        if idx < len(search_results["flights"]):
            detailed["flights"]["return"] = search_results["flights"][idx]
    
    # Expand hotels
    hotel_ref = blueprint.get("hotels", {}).get("hotel_ref")
    if hotel_ref and "hotels" in search_results:
        idx = int(hotel_ref.split("_")[1])
        if idx < len(search_results["hotels"]):
            hotel = search_results["hotels"][idx].copy()
            hotel.update({
                "check_in": blueprint.get("hotels", {}).get("check_in"),
                "check_out": blueprint.get("hotels", {}).get("check_out"),
                "nights": blueprint.get("hotels", {}).get("nights"),
            })
            detailed["hotels"] = hotel
    
    # Expand activities
    for activity_item in blueprint.get("activities", []):
        activity_ref = activity_item.get("activity_ref")
        if activity_ref and "activities" in search_results:
            idx = int(activity_ref.split("_")[1])
            if idx < len(search_results["activities"]):
                activity = search_results["activities"][idx].copy()
                activity["date"] = activity_item.get("date")
                detailed["activities"].append(activity)
    
    # Add cost summary
    detailed["estimated_cost"] = blueprint.get("estimated_cost")
    
    return detailed


def list_verification_results(limit: int = 100):
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


def format_complete_itinerary(verification_result: Dict[str, Any]) -> str:
    """
    Format the complete itinerary for user display.
    
    Args:
        verification_result: Result from verify_and_format_itinerary()
    
    Returns:
        Formatted string with complete trip details
    """
    itinerary = verification_result.get("itinerary")
    if not itinerary:
        return "Complete itinerary details not available"
    
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("✈️  COMPLETE TRAVEL ITINERARY")
    lines.append("=" * 70)
    
    # Validity status
    if verification_result.get("is_valid"):
        lines.append("\n✅ STATUS: APPROVED")
    else:
        lines.append("\n❌ STATUS: REQUIRES REVISION")
        if verification_result.get("issues"):
            lines.append("Issues:")
            for issue in verification_result["issues"]:
                lines.append(f"  • {issue}")
    
    # Flights
    if itinerary.get("flights"):
        lines.append("\n" + "-" * 70)
        lines.append("✈️  FLIGHTS")
        lines.append("-" * 70)
        
        outbound = itinerary["flights"].get("outbound")
        if outbound:
            lines.append(f"\nOUTBOUND FLIGHT:")
            for key, value in outbound.items():
                lines.append(f"  • {key}: {value}")
        
        return_flight = itinerary["flights"].get("return")
        if return_flight:
            lines.append(f"\nRETURN FLIGHT:")
            for key, value in return_flight.items():
                lines.append(f"  • {key}: {value}")
    
    # Hotels
    if itinerary.get("hotels"):
        lines.append("\n" + "-" * 70)
        lines.append("🏨 HOTELS")
        lines.append("-" * 70)
        
        hotel = itinerary["hotels"]
        for key, value in hotel.items():
            if key not in ["check_in", "check_out", "nights"]:
                lines.append(f"  • {key}: {value}")
        
        if hotel.get("check_in"):
            lines.append(f"\n  CHECK-IN:  {hotel.get('check_in')}")
        if hotel.get("check_out"):
            lines.append(f"  CHECK-OUT: {hotel.get('check_out')}")
        if hotel.get("nights"):
            lines.append(f"  DURATION:  {hotel.get('nights')} nights")
    
    # Activities
    if itinerary.get("activities"):
        lines.append("\n" + "-" * 70)
        lines.append("🎯 ACTIVITIES & DINING")
        lines.append("-" * 70)
        
        for i, activity in enumerate(itinerary["activities"], 1):
            date = activity.get("date", "TBD")
            lines.append(f"\nDay - {date}:")
            for key, value in activity.items():
                if key != "date":
                    lines.append(f"  • {key}: {value}")
    
    # Cost Summary
    if itinerary.get("estimated_cost") is not None:
        lines.append("\n" + "-" * 70)
        lines.append("💰 COST SUMMARY")
        lines.append("-" * 70)
        lines.append(f"  Total Estimated Cost: ${itinerary.get('estimated_cost'):,.2f}")
    
    # Final message
    lines.append("\n" + "=" * 70)
    if verification_result.get("final_message_to_user"):
        lines.append(f"📝 {verification_result['final_message_to_user']}")
    lines.append("=" * 70)
    
    return "\n".join(lines)
