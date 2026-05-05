from typing import Any, Dict, List, Tuple, Optional
import json
import os
from datetime import date, datetime

from config import MAX_AGENT_TURNS, CANDIDATES_DIR
from llm import call_llm, call_llm_structured, extract_text
from tools.dispatch import get_serp_manager, create_tool_result_message, dispatch_tool
from tools.schemas import ACTIVITIES_TOOLS, LOGISTICS_TOOLS
from state import TravelConstraints, TravelNeeds


# ============================================================================
# Candidate Data Persistence
# ============================================================================

def _save_search_candidate(
    task_id: str,
    category: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Any,
) -> None:
    """Save search result as candidate for later retrieval."""
    candidate = {
        "task_id": task_id,
        "category": category,
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_result": tool_result,
    }
    
    candidates_dir = os.path.join(CANDIDATES_DIR, task_id)
    os.makedirs(candidates_dir, exist_ok=True)
    
    category_file = os.path.join(candidates_dir, f"{category}_candidates.json")
    
    try:
        candidates_list = []
        if os.path.exists(category_file):
            with open(category_file, "r", encoding="utf-8") as f:
                candidates_list = json.load(f)
        
        candidates_list.append(candidate)
        
        with open(category_file, "w", encoding="utf-8") as f:
            json.dump(candidates_list, f, indent=2, ensure_ascii=False)
        
        print(f"  [Saved] {category} candidates -> {category_file} ({len(candidates_list)} total)")
    except (IOError, json.JSONDecodeError) as e:
        print(f"  [Warning] Failed to save search candidate: {e}")


def retrieve_candidates(task_id: str, category: str) -> List[Dict[str, Any]]:
    """Load saved candidates for a task/category from disk."""
    category_file = os.path.join(CANDIDATES_DIR, task_id, f"{category}_candidates.json")
    if not os.path.exists(category_file):
        return []
    try:
        with open(category_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return []


def list_candidate_tasks() -> List[str]:
    """List all task IDs with saved candidates."""
    if not os.path.isdir(CANDIDATES_DIR):
        return []
    return [d for d in os.listdir(CANDIDATES_DIR) 
            if os.path.isdir(os.path.join(CANDIDATES_DIR, d))]


# ============================================================================
# IATA Airport Code Mapping (city name -> code)
# ============================================================================

_CITY_TO_IATA = {
    "new york": "JFK", "nyc": "JFK", "new york city": "JFK",
    "los angeles": "LAX", "la": "LAX",
    "chicago": "ORD",
    "houston": "IAH",
    "phoenix": "PHX",
    "philadelphia": "PHL",
    "san antonio": "SAT",
    "san diego": "SAN",
    "dallas": "DFW",
    "san jose": "SJC",
    "austin": "AUS",
    "jacksonville": "JAX",
    "san francisco": "SFO", "sf": "SFO",
    "seattle": "SEA",
    "denver": "DEN",
    "washington": "DCA", "washington dc": "DCA", "dc": "DCA",
    "boston": "BOS",
    "nashville": "BNA",
    "detroit": "DTW",
    "portland": "PDX",
    "las vegas": "LAS",
    "memphis": "MEM",
    "atlanta": "ATL",
    "miami": "MIA",
    "orlando": "MCO",
    "minneapolis": "MSP",
    "honolulu": "HNL",
    "anchorage": "ANC",
    "london": "LHR",
    "paris": "CDG",
    "tokyo": "NRT",
    "rome": "FCO",
    "barcelona": "BCN",
    "amsterdam": "AMS",
    "frankfurt": "FRA",
    "dubai": "DXB",
    "singapore": "SIN",
    "hong kong": "HKG",
    "sydney": "SYD",
    "toronto": "YYZ",
    "vancouver": "YVR",
    "cancun": "CUN",
    "mexico city": "MEX",
    "seoul": "ICN",
    "bangkok": "BKK",
    "mumbai": "BOM",
    "delhi": "DEL", "new delhi": "DEL",
    "istanbul": "IST",
    "lisbon": "LIS",
    "madrid": "MAD",
    "berlin": "BER",
    "zurich": "ZRH",
    "vienna": "VIE",
    "taipei": "TPE",
    "osaka": "KIX",
}


def _llm_resolve_iata(city: str) -> str:
    """Ask a cheap LLM to resolve a city name to its IATA airport code."""
    schema = {
        "type": "object",
        "properties": {
            "iata_code": {
                "type": "string",
                "description": "The 3-letter IATA airport code for the city's primary commercial airport",
            }
        },
        "required": ["iata_code"],
    }
    result = call_llm_structured(
        messages=[{"role": "user", "content": f"What is the 3-letter IATA airport code for the primary commercial airport in: {city}"}],
        schema=schema,
        system="You are an aviation data lookup. Return ONLY the standard 3-letter IATA code for the city's main commercial airport. For example: New York -> JFK, London -> LHR, Tokyo -> NRT.",
    )
    code = result.get("iata_code", "").strip().upper()
    if len(code) == 3 and code.isalpha():
        # Cache for future lookups
        _CITY_TO_IATA[city.lower()] = code
        print(f"  [IATA] LLM resolved '{city}' -> {code} (cached)")
        return code
    print(f"  [Warning] LLM returned invalid IATA '{code}' for '{city}', passing city as-is")
    return city


def _to_iata(city_or_code: str) -> str:
    """Convert a city name to IATA code. Uses static dict first, then LLM fallback."""
    s = city_or_code.strip()
    # Already looks like an IATA code
    if 2 <= len(s) <= 4 and s.isalpha() and s.isupper():
        return s
    code = _CITY_TO_IATA.get(s.lower())
    if code:
        return code
    # LLM fallback for unknown cities
    return _llm_resolve_iata(s)


# ============================================================================
# Step 1: Search & Save All Candidates (Direct SerpAPI, No LLM)
# ============================================================================

def search_flight_candidates(
    constraints: TravelConstraints,
    task_id: str,
    topk_limit: int = 20,
) -> List[Dict]:
    """
    Search flights via SerpAPI and save raw data to disk.
    Requires: origin, destination, start_date, end_date.
    
    Returns:
        List of flight search result dicts, e.g. [{"best_flights": [...], "other_flights": [...]}]
    """
    if not constraints.is_ready_for_flight():
        missing = []
        if not constraints.origin: missing.append("origin")
        if not constraints.destination: missing.append("destination")
        if not constraints.start_date: missing.append("start_date")
        if not constraints.end_date: missing.append("end_date")
        print(f"  [Skip] Flights: missing {', '.join(missing)}")
        return []

    serp = get_serp_manager()
    origin_code = _to_iata(constraints.origin)
    dest_code = _to_iata(constraints.destination)
    print(f"  [Search] Flights: {constraints.origin}({origin_code}) -> {constraints.destination}({dest_code}) ({constraints.start_date} to {constraints.end_date})")
    flight_result, count = serp.search_flights(
        origin=origin_code,
        destination=dest_code,
        departure_date=constraints.start_date,
        return_date=constraints.end_date,
        task_id=task_id,
        topk_limit=topk_limit,
    )
    _save_search_candidate(task_id, "flights", "search_flights", {
        "origin": constraints.origin,
        "destination": constraints.destination,
        "departure_date": constraints.start_date,
        "return_date": constraints.end_date,
    }, flight_result)
    print(f"  [Found] {count} flight options")

    return [flight_result]


def search_hotel_candidates(
    constraints: TravelConstraints,
    task_id: str,
    topk_limit: int = 20,
) -> List[Dict]:
    """
    Search hotels via SerpAPI and save raw data to disk.
    Requires: destination, start_date (check_in), end_date (check_out).
    
    Returns:
        List of hotel search result dicts, e.g. [{"properties": [...]}]
    """
    if not constraints.is_ready_for_hotel():
        missing = []
        if not constraints.destination: missing.append("destination")
        if not constraints.start_date: missing.append("start_date/check_in")
        if not constraints.end_date: missing.append("end_date/check_out")
        print(f"  [Skip] Hotels: missing {', '.join(missing)}")
        return []

    serp = get_serp_manager()
    # Build location query: append hotel_location for area-specific results
    location_query = constraints.destination
    if constraints.hotel_location:
        location_query = f"{constraints.hotel_location} {constraints.destination}"
    print(f"  [Search] Hotels: {location_query} ({constraints.start_date} to {constraints.end_date})")
    hotel_result, count = serp.search_hotels(
        location=location_query,
        check_in=constraints.start_date,
        check_out=constraints.end_date or constraints.start_date,
        adults=constraints.num_travelers,
        task_id=task_id,
        topk_limit=topk_limit,
    )
    _save_search_candidate(task_id, "hotels", "search_hotels", {
        "location": constraints.destination,
        "check_in": constraints.start_date,
        "check_out": constraints.end_date,
        "adults": constraints.num_travelers,
    }, hotel_result)
    print(f"  [Found] {count} hotel options")
    return [hotel_result]


def search_activity_candidates(
    constraints: TravelConstraints,
    task_id: str,
    topk_limit: int = 20,
) -> List[Dict]:
    """
    Search activities/restaurants via SerpAPI and save raw data to disk.
    Requires: destination.
    
    Returns:
        List of activity search result dicts, e.g. [{"local_results": [...]}]
    """
    if not constraints.destination:
        print(f"  [Skip] Activities: missing destination")
        return []

    serp = get_serp_manager()
    results = []
    queries = constraints.interests if constraints.interests else ["things to do"]
    if constraints.dietary_needs:
        queries.extend([f"{d} restaurants" for d in constraints.dietary_needs])

    for query in queries:
        print(f"  [Search] Activities: '{query}' in {constraints.destination}")
        activity_result, count = serp.search_places(
            query=query,
            location=constraints.destination,
            task_id=task_id,
            topk_limit=topk_limit,
        )
        results.append(activity_result)
        _save_search_candidate(task_id, "activities", "search_places", {
            "query": query,
            "location": constraints.destination,
        }, activity_result)
        print(f"  [Found] {count} activity options")

    return results


def search_and_save_candidates(
    constraints: TravelConstraints,
    needs: TravelNeeds,
    task_id: str,
) -> Dict[str, List]:
    """
    Convenience wrapper: calls individual search functions based on needs.
    
    Returns:
        {
            "flights": [{"best_flights": [...], "other_flights": [...]}],
            "hotels": [{"properties": [...]}],
            "activities": [{"local_results": [...]}]
        }
    """
    results: Dict[str, List] = {"flights": [], "hotels": [], "activities": []}

    if needs.flight:
        results["flights"] = search_flight_candidates(constraints, task_id)

    if needs.hotel:
        results["hotels"] = search_hotel_candidates(constraints, task_id)

    if needs.activity:
        results["activities"] = search_activity_candidates(constraints, task_id)

    return results


# ============================================================================
# Step 2: Top-K Filtering (Programmatic) + LLM Selection
# ============================================================================

def _extract_flight_price(flight: Dict) -> float:
    """Extract price from a flight result."""
    if isinstance(flight.get("price"), (int, float)):
        return flight["price"]
    # Try nested structure
    for leg in flight.get("flights", []):
        if isinstance(leg.get("price"), (int, float)):
            return leg["price"]
    return float('inf')


def _extract_hotel_price(hotel: Dict) -> float:
    """Extract nightly rate from a hotel result."""
    rate = hotel.get("rate_per_night", {})
    if isinstance(rate, dict):
        return rate.get("extracted_lowest", float('inf'))
    return float('inf')


def _filter_top_k_flights(raw_results: List[Dict], k: int = 5) -> List[Dict]:
    """Flatten flights and return the cheapest k.

    No flight-specific hard constraints exist at the filter stage
    (dates/route are already encoded in the search query).
    Interest-based preferences (nonstop, morning departure, …) are left
    for the LLM selector which receives the full constraints JSON.
    """
    all_flights = []
    for result in raw_results:
        all_flights.extend(result.get("best_flights", []))
        all_flights.extend(result.get("other_flights", []))
    all_flights.sort(key=_extract_flight_price)
    return all_flights[:k]


def _filter_top_k_hotels(raw_results: List[Dict], k: int = 5,
                         min_star: int | None = None,
                         max_price_per_night: float | None = None) -> List[Dict]:
    """Flatten hotels, prioritise those meeting HARD constraints, then by price.

    Hard constraints checked (only when provided):
      • star_class >= min_star   (only when hotel_rating_priority == 'hard')
      • price_per_night <= max_price_per_night

    Priority 1 – hotels satisfying ALL applicable hard constraints, sorted by price.
    Priority 2 – hotels satisfying at least one hard constraint, sorted by
                 number of constraints met (desc) then price.
    Priority 3 – remaining hotels sorted by closeness to star requirement
                 (desc star) then price.
    Fill up to k total.
    """
    all_hotels = []
    for result in raw_results:
        all_hotels.extend(result.get("properties", []))

    has_constraints = min_star is not None or max_price_per_night is not None
    if not has_constraints or not all_hotels:
        all_hotels.sort(key=_extract_hotel_price)
        return all_hotels[:k]

    def _star(h: Dict) -> float:
        hc = h.get("extracted_hotel_class") or h.get("hotel_class", 0)
        return float(hc) if isinstance(hc, (int, float)) else 0

    def _meets(h: Dict) -> int:
        """Count how many hard constraints this hotel satisfies."""
        score = 0
        if min_star is not None and _star(h) >= min_star:
            score += 1
        if max_price_per_night is not None and _extract_hotel_price(h) <= max_price_per_night:
            score += 1
        return score

    num_constraints = (1 if min_star is not None else 0) + (1 if max_price_per_night is not None else 0)

    full_match = [h for h in all_hotels if _meets(h) == num_constraints]
    partial = [h for h in all_hotels if 0 < _meets(h) < num_constraints]
    rest = [h for h in all_hotels if _meets(h) == 0]

    full_match.sort(key=_extract_hotel_price)
    partial.sort(key=lambda h: (-_meets(h), _extract_hotel_price(h)))
    # Sort rest by closest star class (descending), then price
    rest.sort(key=lambda h: (-_star(h), _extract_hotel_price(h)))
    return (full_match + partial + rest)[:k]


def _filter_top_k_activities(raw_results: List[Dict], k: int = 8) -> List[Dict]:
    """Flatten activities and return the top-k by rating.

    Activities have no programmatic hard constraints at the filter stage.
    Interest-based preference matching is left for the LLM selector
    which receives the full constraints JSON including interests.
    """
    all_activities = []
    for result in raw_results:
        all_activities.extend(result.get("local_results", []))
    all_activities.sort(key=lambda a: a.get("rating", 0), reverse=True)
    return all_activities[:k]


def _slim_flight(f: Dict) -> Dict:
    """Keep only LLM-relevant flight fields to save tokens."""
    slim: Dict[str, Any] = {}
    if "price" in f:
        slim["price"] = f["price"]
    if "total_duration" in f:
        slim["total_duration"] = f["total_duration"]
    if "type" in f:
        slim["type"] = f["type"]
    # Top-level extensions (e.g. "Checked baggage for a fee")
    if "extensions" in f:
        slim["extensions"] = f["extensions"]
    # Slim each flight leg
    if "flights" in f:
        slim_legs = []
        for leg in f["flights"]:
            sl = {}
            for key in ("departure_airport", "arrival_airport", "duration",
                        "airline", "flight_number", "travel_class", "legroom"):
                if key in leg:
                    sl[key] = leg[key]
            slim_legs.append(sl)
        slim["flights"] = slim_legs
    # Keep layovers (already small)
    if "layovers" in f:
        slim["layovers"] = [{"duration": l.get("duration"), "name": l.get("name")}
                            for l in f["layovers"]]
    return slim


def _slim_hotel(h: Dict) -> Dict:
    """Keep only LLM-relevant hotel fields to save tokens."""
    slim = {}
    for key in ("name", "hotel_class", "extracted_hotel_class",
                "overall_rating", "rate_per_night",
                "total_rate", "amenities", "address"):
        if key in h:
            slim[key] = h[key]
    return slim


def _slim_activity(a: Dict) -> Dict:
    """Keep only LLM-relevant activity fields to save tokens."""
    slim = {}
    for key in ("title", "rating", "price",
                "type", "address", "description"):
        if key in a:
            slim[key] = a[key]
    return slim


# Schema for LLM selection output
SELECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "itinerary": {
            "type": "object",
            "description": "The selected travel plan with best options",
            "properties": {
                "flights": {
                    "type": "object",
                    "description": "Selected flight details (omit if not needed)",
                    "properties": {
                        "outbound": {"type": "object", "description": "Selected outbound flight with full details"},
                        "return": {"type": "object", "description": "Selected return flight with full details"},
                    }
                },
                "hotels": {
                    "type": "object",
                    "description": "Selected hotel with full details (omit if not needed)",
                },
                "activities": {
                    "type": "array",
                    "description": "Selected activities scheduled across trip days",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day_number": {"type": "integer", "description": "Which day of the trip (1, 2, 3...)"},
                            "date": {"type": "string", "description": "YYYY-MM-DD"},
                            "time": {"type": "string", "description": "Suggested start time, e.g. '09:00', '14:30', '19:00'"},
                            "duration_hours": {"type": "number", "description": "Estimated duration in hours (e.g. 1.5, 2, 3)"},
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["attraction", "restaurant", "tour", "museum", "entertainment", "shopping", "sports"]},
                            "description": {"type": "string"},
                            "location": {"type": "string"},
                            "price_per_person": {"type": "number"},
                            "total_price": {"type": "number"},
                        },
                        "required": ["day_number", "date", "time", "duration_hours", "name", "type", "price_per_person"],
                    },
                },
                "estimated_total_cost": {
                    "type": "number",
                    "description": "Total estimated cost in USD for all selected components",
                },
            },
        },
        "constraints_met": {
            "type": "boolean",
            "description": "True if ALL hard constraints and budget are satisfied by the selection",
        },
        "unmet_constraints": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of constraints that could NOT be satisfied (empty if all met)",
        },
        "closest_alternative": {
            "type": "object",
            "description": "If constraints_met=false, provide the closest feasible plan that partially meets constraints. Same structure as itinerary.",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of why these options were selected",
        },
        "final_message_to_user": {
            "type": "string",
            "description": "Friendly summary message for the user",
        },
    },
    "required": ["itinerary", "constraints_met", "unmet_constraints", "reasoning", "final_message_to_user"],
}


def select_top_k(
    task_id: str,
    constraints_json: str,
    needs: TravelNeeds,
    search_results: Dict[str, List],
    top_k: int = 8,
) -> Dict[str, Any]:
    """
    Step 2: Filter to top-K candidates per category (programmatic),
    then use LLM to select the best combination.
    
    Args:
        task_id: Task identifier
        constraints_json: JSON string of constraints
        needs: What the user needs
        search_results: Raw results from search_and_save_candidates()
        top_k: Number of top candidates per category
    
    Returns:
        Selection result matching SELECTOR_SCHEMA
    """
    # Parse constraints for programmatic filtering (hard constraints only)
    _constraints = json.loads(constraints_json) if constraints_json else {}
    _rating_priority = _constraints.get("hotel_rating_priority", "soft")
    # Star rating is a hard constraint only when priority == "hard"
    _min_star = _constraints.get("preferred_hotel_rating") if _rating_priority == "hard" else None
    _max_price = _constraints.get("hotel_budget_per_night")

    # Programmatic top-K filtering (hard-constraint priority)
    top_flights = _filter_top_k_flights(search_results.get("flights", []), top_k) if needs.flight else []
    top_hotels = _filter_top_k_hotels(search_results.get("hotels", []), top_k, min_star=_min_star, max_price_per_night=_max_price) if needs.hotel else []
    top_activities = _filter_top_k_activities(search_results.get("activities", []), top_k + 5) if needs.activity else []
    
    # Build candidate summary for LLM (slimmed to constraint/interest-relevant fields)
    candidates_text = ""
    if top_flights:
        candidates_text += f"\n=== TOP {len(top_flights)} FLIGHT CANDIDATES (round-trip) ===\n"
        for i, f in enumerate(top_flights):
            candidates_text += f"[Flight {i}] {json.dumps(_slim_flight(f), indent=2, ensure_ascii=False)}\n"
    
    if top_hotels:
        candidates_text += f"\n=== TOP {len(top_hotels)} HOTEL CANDIDATES ===\n"
        for i, h in enumerate(top_hotels):
            candidates_text += f"[Hotel {i}] {json.dumps(_slim_hotel(h), indent=2, ensure_ascii=False)}\n"
    
    if top_activities:
        candidates_text += f"\n=== TOP {len(top_activities)} ACTIVITY CANDIDATES ===\n"
        for i, a in enumerate(top_activities):
            candidates_text += f"[Activity {i}] {json.dumps(_slim_activity(a), indent=2, ensure_ascii=False)}\n"
    
    system_prompt = f"""You are the Selector for Nomad Travel Agent.
Today's date is {date.today().isoformat()}.

Your job: Given the user's constraints and a set of top-K candidates for each category,
select the BEST combination that satisfies all constraints.

USER CONSTRAINTS:
{constraints_json}

SELECTION CRITERIA:
- Pick the best VALUE (balance of price, quality, convenience)
- Respect ALL hard constraints (dates, locations)
- Stay within budget if specified
- If budget or hard constraints CANNOT be met by any candidate:
  1. Set constraints_met = false
  2. List which constraints are unmet
  3. Provide closest_alternative with the best feasible option
- Include ALL details from the original candidate data in your selection
- For FLIGHTS: You MUST select BOTH an outbound AND a return flight with FULL details.
  The outbound and return candidates are listed separately. Pick one outbound flight,
  then pick the best matching return flight from that outbound's return candidates.
  Copy ALL fields (departure_airport, arrival_airport, duration, airline, flight_number,
  legroom, extensions, price, carbon_emissions, etc.) into both flights.outbound and flights.return.

COMPONENTS NEEDED:
- Flight: {"YES — select BOTH outbound AND return with full details" if needs.flight else "NO"}
- Hotel: {"YES" if needs.hotel else "NO"}  
- Activity: {"YES — schedule each activity on a specific day with time and estimated duration" if needs.activity else "NO"}

ACTIVITY SCHEDULING RULES (when activities are needed):
- Distribute activities across the trip days (day 1 = arrival day, last day = departure day)
- Assign a realistic start time (e.g. morning 09:00-11:00, afternoon 13:00-16:00, evening 18:00-21:00)
- Estimate duration_hours based on activity type (restaurants ~1.5h, museums/tours ~2-3h, attractions ~1-2h, entertainment ~2-3h)
- Avoid time conflicts within the same day — leave reasonable gaps between activities
- On arrival day, schedule activities for the afternoon/evening only
- On departure day, schedule activities for the morning only
- Set date = start_date + (day_number - 1)

ACTIVITY PRICING:
- Search results often lack price data for attractions/tours.
- When a candidate has no "price" field, ESTIMATE price_per_person using your knowledge:
  - Free: public parks, beaches, tide pools, street markets, window shopping
  - $0-15: self-guided walking tours, botanical gardens, minor museums
  - $15-40: major museums, zoos, aquariums, guided city tours
  - $40-80: whale watching, helicopter tours, theme parks, Broadway shows
  - $80+: premium experiences, multi-hour excursions, VIP tours
- For restaurants: estimate based on cuisine and city (fast casual $10-20, mid-range $20-40, fine dining $50+)
- Always set price_per_person even if estimated — the plan needs cost data for budget checks
"""

    messages = [
        {
            "role": "user",
            "content": f"Here are the top candidates. Select the best combination:\n{candidates_text}",
        }
    ]
    
    print(f"  [Selector] LLM selecting from {len(top_flights)} flights, {len(top_hotels)} hotels, {len(top_activities)} activities...")
    
    result = call_llm_structured(
        messages=messages,
        schema=SELECTOR_SCHEMA,
        system=system_prompt,
    )
    
    return result


# ============================================================================
# Backward Compatibility: Legacy specialist functions
# ============================================================================

def _categorize_search_result(tool_name: str, result: Any) -> str:
    """Categorize search result by tool name."""
    tool_lower = tool_name.lower()
    if 'flight' in tool_lower:
        return 'flights'
    elif 'hotel' in tool_lower:
        return 'hotels'
    elif 'activity' in tool_lower or 'restaurant' in tool_lower or 'place' in tool_lower:
        return 'activities'
    return 'unknown'


def run_specialist(
    task_description: str, 
    tools: List[Dict[str, Any]], 
    constraints_json: str,
    task_id: str = None
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Legacy ReAct tool-calling loop (kept for backward compatibility).
    New code should use search_and_save_candidates() + select_top_k() instead.
    """

    system_prompt = f"""You are a specialized Nomad Sub-Agent.
Today's date is {date.today().isoformat()}.
Your task: {task_description}

You must adhere strictly to these constraints:
{constraints_json}

YOUR JOB - THREE PHASES:

PHASE 1: SEARCH
- Search for multiple options in each category

PHASE 2: FILTER & RANK
- Rank and present top 5 in each category

PHASE 3: SUMMARIZE
- Present the TOP candidates with full details

Return a summary of the TOP candidates with their rankings and details."""

    messages = [
        {"role": "user", "content": "Search, filter for top candidates, and present them with ranking criteria."}
    ]

    search_results = {"flights": [], "hotels": [], "activities": []}
    verifier_context = {
        "specialist_reasoning": [],
        "search_coverage": {"flights": 0, "hotels": 0, "activities": 0},
        "key_decisions": [],
        "budget_analysis": "",
        "risk_factors": [],
        "recommendations": "",
        "tool_calls_summary": [],
    }

    turn = 0
    while turn < MAX_AGENT_TURNS:
        print(f"  [Specialist Turn {turn + 1}] Thinking...")
        response = call_llm(messages=messages, system=system_prompt, tools=tools)
        stop_reason = response.get("stop_reason")
        content_blocks = response.get("content", [])
        
        for block in content_blocks:
            if block.get("type") == "text":
                reasoning = block.get("text", "").strip()
                if reasoning:
                    verifier_context["specialist_reasoning"].append(reasoning)
        
        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason != "tool_use":
            draft_text = extract_text(response)
            verifier_context["final_draft"] = draft_text
            verifier_context["total_searches"] = sum(verifier_context["search_coverage"].values())
            return draft_text, search_results, verifier_context

        tool_results = []
        for block in content_blocks:
            if block["type"] == "tool_use":
                tool_use_id = block["id"]
                tool_name = block["name"]
                tool_args = block["input"].copy()
                
                result, candidate_count = dispatch_tool(tool_name, {**tool_args, "task_id": task_id, "turn": turn})
                
                category = _categorize_search_result(tool_name, result)
                if category in search_results and isinstance(result, dict) and "error" not in result:
                    search_results[category].append(result)
                    verifier_context["search_coverage"][category] += candidate_count
                
                if task_id and isinstance(result, dict) and "error" not in result:
                    _save_search_candidate(task_id, category, tool_name, tool_args, result)
                
                verifier_context["tool_calls_summary"].append({
                    "tool": tool_name, "category": category, "candidates": candidate_count,
                })
                
                category = _categorize_search_result(tool_name, result)
                if category == "flights":
                    items = result.get("best_flights", []) + result.get("other_flights", [])
                elif category == "hotels":
                    items = result.get("properties", [])
                elif category == "activities":
                    items = result.get("local_results", [])
                else:
                    items = []
                if category in search_results:
                    search_results[category].extend(items)
                tool_results.append(create_tool_result_message(tool_use_id, tool_name, result))

        messages.append({"role": "user", "content": tool_results})
        turn += 1

    raise RuntimeError(f"Reached max turns ({MAX_AGENT_TURNS}) without a final answer.")


def run_logistics_specialist(constraints_json: str, task_id: str = None) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Legacy: Specialist for finding flights and hotels."""
    return run_specialist(
        task_description="Find the best flights and hotels for the trip.",
        tools=LOGISTICS_TOOLS,
        constraints_json=constraints_json,
        task_id=task_id,
    )


def run_activities_specialist(constraints_json: str, task_id: str = None) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Legacy: Specialist for finding restaurants and things to do."""
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
