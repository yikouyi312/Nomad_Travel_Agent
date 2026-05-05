from typing import Any, Dict, List, Optional
import json
import os
from datetime import datetime

from llm import call_llm_structured
from config import VERIFICATION_DIR
from state import TravelConstraints
from agents.specialist import _to_iata

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


# ============================================================================
# Constraint Validation & Negotiation (New Pipeline)
# ============================================================================

def validate_plan(
    selection_result: Dict[str, Any],
    constraints: TravelConstraints,
) -> Dict[str, Any]:
    """
    Robust plan validation: programmatic checks first, then filtered LLM claims.

    Programmatic (authoritative): budget, airports, hotel star, hotel price, dates.
    LLM (supplementary): only qualitative issues the code can't verify, with
    budget/airport/date/star/price claims filtered out to prevent hallucination.

    Returns:
        {
            "valid": bool,
            "unmet_constraints": [str],
            "plan": dict,
            "closest_alternative": dict | None,
        }
    """
    if not isinstance(selection_result, dict):
        return {
            "valid": False,
            "unmet_constraints": [f"LLM returned non-dict: {str(selection_result)[:200]}"],
            "plan": {},
            "closest_alternative": None,
        }

    itinerary = selection_result.get("itinerary", {})
    if not isinstance(itinerary, dict):
        itinerary = {}
    unmet: List[str] = []

    # ── 1. Budget ──
    if constraints.budget_usd and itinerary.get("estimated_total_cost"):
        try:
            total_cost = float(itinerary["estimated_total_cost"])
        except (TypeError, ValueError):
            total_cost = 0
        if total_cost > constraints.budget_usd:
            unmet.append(
                f"Budget exceeded: ${total_cost:.0f} vs limit ${constraints.budget_usd:.0f}"
            )

    # ── 2. Flights ──
    flights = itinerary.get("flights", {})
    if isinstance(flights, dict) and flights:
        outbound = flights.get("outbound", {}) if isinstance(flights.get("outbound"), dict) else {}
        return_fl = flights.get("return", {}) if isinstance(flights.get("return"), dict) else {}

        # 2a. Departure airport
        if constraints.origin and outbound:
            dep = outbound.get("departure_airport", {})
            dep_id = dep.get("id", "") if isinstance(dep, dict) else ""
            if dep_id and _to_iata(dep_id) != _to_iata(constraints.origin):
                unmet.append(f"Departure airport: {dep_id} vs expected {constraints.origin}")

        # 2b. Arrival airport
        if constraints.destination and outbound:
            arr = outbound.get("arrival_airport", {})
            arr_id = arr.get("id", "") if isinstance(arr, dict) else ""
            if arr_id and _to_iata(arr_id) != _to_iata(constraints.destination):
                unmet.append(f"Arrival airport: {arr_id} vs expected {constraints.destination}")

        # 2c. Return flight mirrors (dest → origin)
        if constraints.origin and return_fl:
            ret_arr = return_fl.get("arrival_airport", {})
            ret_arr_id = ret_arr.get("id", "") if isinstance(ret_arr, dict) else ""
            if ret_arr_id and _to_iata(ret_arr_id) != _to_iata(constraints.origin):
                unmet.append(f"Return arrival: {ret_arr_id} vs expected {constraints.origin}")

    # ── 3. Hotel star rating ──
    hotel = itinerary.get("hotels", {})
    if isinstance(hotel, dict) and constraints.preferred_hotel_rating:
        star = hotel.get("extracted_hotel_class") or hotel.get("hotel_class") or hotel.get("star_rating")
        if star is not None:
            try:
                if int(star) < constraints.preferred_hotel_rating:
                    unmet.append(
                        f"Hotel star: {star}-star vs minimum {constraints.preferred_hotel_rating}-star"
                    )
            except (TypeError, ValueError):
                pass

    # ── 4. Hotel budget per night ──
    if isinstance(hotel, dict) and constraints.hotel_budget_per_night:
        rate = hotel.get("rate_per_night", {})
        nightly = None
        if isinstance(rate, dict):
            nightly = rate.get("extracted_lowest") or rate.get("lowest")
        elif isinstance(rate, (int, float)):
            nightly = rate
        # Also try price_per_night directly
        if nightly is None:
            nightly = hotel.get("price_per_night")
        if nightly is not None:
            try:
                nightly_f = float(str(nightly).replace("$", "").replace(",", ""))
                if nightly_f > constraints.hotel_budget_per_night:
                    unmet.append(
                        f"Hotel rate: ${nightly_f:.0f}/night vs limit ${constraints.hotel_budget_per_night:.0f}/night"
                    )
            except (TypeError, ValueError):
                pass

    # ── 5. LLM qualitative issues (filtered) ──
    # Only keep items the code above can't verify (e.g. "no pet-friendly option found")
    PROGRAMMATIC_KEYWORDS = [
        "budget", "cost", "price", "exceed", "over",         # budget
        "airport", "departure", "arrival", "origin", "dest",  # airports
        "date", "return flight", "return leg",                 # dates/flights
        "star", "rating",                                      # hotel star
        "per night", "nightly",                                # hotel price
    ]
    llm_unmet = selection_result.get("unmet_constraints", [])
    if isinstance(llm_unmet, list):
        for item in llm_unmet:
            if not isinstance(item, str):
                continue
            item_lower = item.lower()
            # Skip if it overlaps with any programmatic check domain
            if any(kw in item_lower for kw in PROGRAMMATIC_KEYWORDS):
                continue
            unmet.append(item)

    # Deduplicate
    unmet = list(dict.fromkeys(unmet))

    return {
        "valid": len(unmet) == 0,
        "unmet_constraints": unmet,
        "plan": itinerary,
        "closest_alternative": selection_result.get("closest_alternative"),
    }


def format_negotiation_message(validation_result: Dict[str, Any]) -> str:
    """
    Format a user-facing message when constraints can't be met.
    Asks user to accept the closest option or adjust constraints.
    
    Args:
        validation_result: Result from validate_plan()
    
    Returns:
        Formatted negotiation message string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("⚠️  SOME CONSTRAINTS COULD NOT BE MET")
    lines.append("=" * 60)
    
    for issue in validation_result.get("unmet_constraints", []):
        lines.append(f"  • {issue}")
    
    lines.append("")
    
    # Show closest alternative if available
    alt = validation_result.get("closest_alternative")
    if alt:
        lines.append("📋 CLOSEST FEASIBLE OPTION:")
        lines.append("-" * 40)
        if alt.get("flights"):
            lines.append(f"  ✈️  Flights: {json.dumps(alt['flights'], indent=4, ensure_ascii=False)}")
        if alt.get("hotels"):
            lines.append(f"  🏨 Hotel: {json.dumps(alt['hotels'], indent=4, ensure_ascii=False)}")
        if alt.get("activities"):
            lines.append(f"  🎯 Activities: {len(alt['activities'])} selected")
        if alt.get("estimated_total_cost"):
            lines.append(f"  💰 Cost: ${alt['estimated_total_cost']:,.0f}")
    else:
        # Fall back to showing the original plan
        plan = validation_result.get("plan", {})
        if plan.get("estimated_total_cost"):
            lines.append(f"  💰 Closest cost: ${plan['estimated_total_cost']:,.0f}")
    
    lines.append("")
    lines.append("OPTIONS:")
    lines.append("  1. Accept this option (type 'accept')")
    lines.append("  2. Adjust your constraints (tell me what to change)")
    lines.append("=" * 60)
    
    return "\n".join(lines)
