"""
Example: Using the Blueprint Pattern with Search Results

This example demonstrates the token-optimized verification flow:
1. Verifier outputs a lightweight blueprint with selection references
2. Search results are saved with the verification for later expansion
3. determine_details() can expand references on-demand

BENEFITS:
- Main verification output: ~100-150 tokens
- Full details only retrieved when explicitly requested
- ~75-80% token reduction in primary agent flow
- All information remains accessible via determine_details()
"""

from agents.verifier import (
    verify_and_format_itinerary,
    determine_details,
    load_verification_result,
)


def example_blueprint_workflow():
    """Demonstrates the blueprint + lazy-load pattern"""
    
    # Step 1: Example search results from specialists
    search_results = {
        "flights": [
            {
                "airline": "Delta",
                "outbound_time": "2026-05-05 08:00 AM",
                "outbound_duration": "5h 30m",
                "price": 450,
            },
            {
                "airline": "United",
                "outbound_time": "2026-05-05 02:00 PM",
                "outbound_duration": "6h 15m",
                "price": 380,
            },
        ],
        "hotels": [
            {
                "name": "Pike Place Hotel",
                "address": "123 Pike St, Seattle, WA",
                "price_per_night": 200,
                "rating": 4.5,
            },
            {
                "name": "Belltown Inn",
                "address": "456 Bell Ave, Seattle, WA",
                "price_per_night": 150,
                "rating": 4.2,
            },
        ],
        "activities": [
            {
                "name": "Space Needle Tour",
                "price": 25,
                "duration": "2 hours",
            },
            {
                "name": "Pike Place Market Visit",
                "price": 0,
                "duration": "3 hours",
            },
        ],
    }
    
    # Step 2: Example draft itinerary from specialists
    draft_text = """
    Proposed 7-day Seattle trip:
    - Outbound: Flight 0 (Delta, $450)
    - Hotel: Pike Place Hotel, check-in May 5, check-out May 12 (7 nights @ $200/night = $1400)
    - Day 1: Space Needle Tour ($25)
    - Day 2: Pike Place Market ($0)
    - Total: $1875
    """
    
    constraints_json = """{
        "origin": "New York",
        "destination": "Seattle",
        "start_date": "2026-05-05",
        "end_date": "2026-05-12",
        "budget_usd": 3000,
        "num_travelers": 1
    }"""
    
    # Step 3: Verifier outputs BLUEPRINT (lightweight)
    # Note: In real usage, pass task_id to auto-save
    blueprint_result = verify_and_format_itinerary(
        draft_text=draft_text,
        constraints_json=constraints_json,
        task_id="example_001",
        search_results=search_results,  # <-- Pass search results for persistence
    )
    
    print("=== VERIFICATION OUTPUT (Blueprint) - ~100-150 tokens ===")
    print(f"Valid: {blueprint_result['is_valid']}")
    print(f"Blueprint: {blueprint_result.get('itinerary_blueprint')}")
    print(f"Message: {blueprint_result.get('final_message_to_user')}\n")
    
    # Step 4: LATER, if you need full details, call determine_details()
    blueprint = blueprint_result.get("itinerary_blueprint")
    expanded = determine_details(blueprint, search_results)
    
    print("=== EXPANDED OUTPUT (Full Details) - only when needed ===")
    print(f"Flights: {expanded['flights']}")
    print(f"Hotels: {expanded['hotels']}")
    print(f"Activities: {expanded['activities']}\n")
    
    # Step 5: You can also load saved results later
    loaded = load_verification_result("example_001")
    if loaded:
        print("=== LOADED FROM DISK ===")
        print(f"Timestamp: {loaded['timestamp']}")
        print(f"Blueprint: {loaded['verification']['itinerary_blueprint']}")
        print(f"Has search results: {'search_results' in loaded}\n")


if __name__ == "__main__":
    example_blueprint_workflow()
