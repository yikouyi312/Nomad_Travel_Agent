"""
Practical examples: SerpManager integration demonstration

Demonstrating three usage patterns:
1. Backward compatible old interface
2. New SerpManager interface
3. Integration with dispatch
"""

from tools.serpapi import SerpManager, search_flights


def example_1_old_interface():
    """Example 1: Backward compatible old interface"""
    print("\n=== Example 1: Old interface (auto-use new cache system) ===\n")

    # First call - API call + save
    flights = search_flights(
        origin="BOS",
        destination="SEA",
        departure_date="2026-05-05",
        return_date="2026-05-12",
    )
    print(f"Flight count: {len(flights.get('best_flights', []))}")

    # Second call - cache hit
    flights_cached = search_flights(
        origin="BOS",
        destination="SEA",
        departure_date="2026-05-05",
        return_date="2026-05-12",
    )
    print(f"Flight count: {len(flights_cached.get('best_flights', []))}")


def example_2_new_interface():
    """Example 2: New SerpManager interface"""
    print("\n=== Example 2: New SerpManager interface ===\n")

    # Create manager
    manager = SerpManager()

    # Search flights
    flights = manager.search_flights(
        origin="LAX",
        destination="JFK",
        departure_date="2026-07-04",
        return_date="2026-07-11",
    )
    print(f"✈️  Flight results: {len(flights.get('best_flights', []))} options")

    # Search hotels
    hotels = manager.search_hotels(
        location="New York, NY",
        check_in="2026-07-04",
        check_out="2026-07-11",
        adults=1,
    )
    print(f"🏨 Hotel results: {len(hotels.get('properties', []))} options")

    # Search places
    places = manager.search_places(
        query="fine dining restaurants",
        location="New York, NY",
    )
    print(f"🍽️  Places results: {len(places.get('local_results', []))} options")


def example_3_with_snapshot():
    """Example 3: For benchmark (with snapshot support)"""
    print("\n=== Example 3: Benchmark snapshot mode ===\n")

    # Create manager with snapshot
    manager = SerpManager(snapshot_path="data/serp_snapshot.json")

    # Use task_id and turn, prioritize snapshot
    flights = manager.search_flights(
        origin="ORD",
        destination="MIA",
        departure_date="2026-04-10",
        return_date="2026-04-17",
        task_id="T1-01",
        turn=1,
    )
    print(f"✈️  Flights: {len(flights.get('best_flights', []))} options")


def example_4_cache_comparison():
    """Example 4: Cache comparison (demonstrates three-layer cache)"""
    print("\n=== Example 4: Cache comparison ===\n")

    manager = SerpManager()

    # Search 1 - API call
    print("First call:")
    result1 = manager.search_hotels(
        location="Boston, MA",
        check_in="2026-03-15",
        check_out="2026-03-18",
    )
    print(f"  Result: {len(result1.get('properties', []))} hotels\n")

    # Search 2 - cache hit (same parameters)
    print("Second call (same parameters):")
    result2 = manager.search_hotels(
        location="Boston, MA",
        check_in="2026-03-15",
        check_out="2026-03-18",
    )
    print(f"  Result: {len(result2.get('properties', []))} hotels\n")

    # Search 3 - API call (different parameters)
    print("Third call (different parameters):")
    result3 = manager.search_hotels(
        location="Boston, MA",
        check_in="2026-03-20",
        check_out="2026-03-25",
    )
    print(f"  Result: {len(result3.get('properties', []))} hotels\n")


if __name__ == "__main__":
    print("🌍 SerpManager integration demo\n")

    try:
        # example_1_old_interface()
        # example_2_new_interface()
        # example_3_with_snapshot()
        example_4_cache_comparison()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Tip: Make sure SERP_API key is set in .env")
