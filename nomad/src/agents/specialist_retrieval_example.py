"""
Example: Using Search Candidate Retrieval

This example demonstrates how to:
1. Save search results as candidates during specialist execution
2. Retrieve candidates by task_id and category
3. Reuse candidates for different itinerary planning scenarios

WORKFLOW:
  Specialist runs (with task_id)
    ↓ Saves each tool result as candidate
  Later, retrieve candidates by task_id + category
    ↓ Use candidates to generate alternative itineraries
  Or, combine candidates from multiple tasks for comparison
"""

from agents.specialist import (
    run_logistics_specialist,
    run_activities_specialist,
    retrieve_candidates,
    list_candidate_tasks,
)
from state import TravelState


def example_save_and_retrieve_candidates():
    """Demonstrates saving candidates during specialist execution and retrieving them"""
    
    # Example constraints
    constraints_json = """{
        "origin": "New York",
        "destination": "Seattle",
        "start_date": "2026-05-05",
        "end_date": "2026-05-12",
        "budget_usd": 3000,
        "num_travelers": 1,
        "dietary_needs": [],
        "interests": ["hiking", "coffee", "tech"]
    }"""
    
    # Create a state to get task_id
    state = TravelState()
    task_id = state.task_id
    print(f"[Task ID] {task_id}\n")
    
    # ===== PHASE 1: RUN SPECIALISTS (saves candidates automatically) =====
    print("[Phase 1] Running specialists and saving candidates...")
    
    # Run logistics specialist - automatically saves flight/hotel candidates
    print("\n  → Running logistics specialist...")
    logistics_draft, logistics_searches = run_logistics_specialist(
        constraints_json=constraints_json,
        task_id=task_id,  # <-- Pass task_id to enable candidate saving
    )
    print(f"  ✓ Found {len(logistics_searches['flights'])} flights, "
          f"{len(logistics_searches['hotels'])} hotels")
    
    # Run activities specialist - automatically saves activity candidates
    print("\n  → Running activities specialist...")
    activities_draft, activities_searches = run_activities_specialist(
        constraints_json=constraints_json,
        task_id=task_id,
    )
    print(f"  ✓ Found {len(activities_searches['activities'])} activities")
    
    # ===== PHASE 2: RETRIEVE CANDIDATES BY CATEGORY =====
    print("\n[Phase 2] Retrieving candidates by category...")
    
    # Retrieve all candidates for this task
    all_candidates = retrieve_candidates(task_id)
    print(f"\n  Saved candidates:")
    for category, candidates in all_candidates.items():
        print(f"    - {category}: {len(candidates)} candidates")
    
    # Retrieve specific category (e.g., only flights)
    print("\n  Retrieving flights only...")
    flight_candidates = retrieve_candidates(task_id, category="flights")
    if "flights" in flight_candidates:
        print(f"    Found {len(flight_candidates['flights'])} flight candidates")
        for i, candidate in enumerate(flight_candidates['flights'][:2]):  # Show first 2
            print(f"      Candidate {i+1}: {candidate['tool_name']} at {candidate['timestamp']}")
    
    # ===== PHASE 3: REUSE CANDIDATES FOR ALTERNATIVE SCENARIOS =====
    print("\n[Phase 3] Example: Reusing candidates for alternatives...")
    
    # You could now:
    # 1. Pick different flights from saved candidates
    # 2. Try different hotel combinations
    # 3. Build multiple itineraries to show to user
    
    hotel_candidates = retrieve_candidates(task_id, category="hotels")
    if "hotels" in hotel_candidates and hotel_candidates['hotels']:
        print(f"\n  Scenario: Building alternative itineraries using saved hotel candidates")
        print(f"    Available hotel options: {len(hotel_candidates['hotels'])}")
        
        for i, hotel_candidate in enumerate(hotel_candidates['hotels'][:2]):
            result = hotel_candidate['tool_result']
            if isinstance(result, list) and len(result) > 0:
                hotel = result[0]
                print(f"      Alternative {i+1}: {hotel.get('name', 'Unknown Hotel')}")
    
    # ===== PHASE 4: LIST ALL TASK IDS WITH CANDIDATES =====
    print("\n[Phase 4] Browsing all saved tasks...")
    
    task_ids = list_candidate_tasks()
    print(f"\n  Tasks with saved candidates: {len(task_ids)}")
    for tid in task_ids[-3:]:  # Show last 3
        print(f"    - {tid}")


def example_cross_task_analysis():
    """Demonstrates retrieving candidates from multiple tasks for comparison"""
    
    # Get list of all tasks
    task_ids = list_candidate_tasks()
    
    print(f"Analyzing candidates from {len(task_ids)} tasks...\n")
    
    # Compile statistics
    stats = {
        "flights": [],
        "hotels": [],
        "activities": [],
    }
    
    for task_id in task_ids[-5:]:  # Last 5 tasks
        task_candidates = retrieve_candidates(task_id)
        
        for category in ["flights", "hotels", "activities"]:
            if category in task_candidates:
                count = len(task_candidates[category])
                stats[category].append({
                    "task_id": task_id,
                    "count": count,
                    "candidates": task_candidates[category]
                })
    
    # Print summary
    print("Summary by category:")
    for category, tasks_data in stats.items():
        if tasks_data:
            total = sum(t["count"] for t in tasks_data)
            print(f"  {category}: {total} candidates across {len(tasks_data)} tasks")


def example_benchmark_evaluation():
    """Demonstrates using candidates for benchmark evaluation"""
    
    # Scenario: Evaluate a benchmark task
    task_id = "T1-01"  # Example benchmark task ID
    
    print(f"Evaluating candidates for benchmark task: {task_id}\n")
    
    # Retrieve all candidates
    candidates = retrieve_candidates(task_id)
    
    for category, candidate_list in candidates.items():
        print(f"{category.upper()} Candidates:")
        print(f"  Total candidates: {len(candidate_list)}")
        
        if candidate_list:
            # Show details of first candidate
            first = candidate_list[0]
            print(f"  First tool called: {first['tool_name']}")
            print(f"  Timestamp: {first['timestamp']}")
            
            if isinstance(first['tool_result'], list) and len(first['tool_result']) > 0:
                item = first['tool_result'][0]
                print(f"  First result keys: {list(item.keys())}")
        print()


if __name__ == "__main__":
    # Uncomment to run examples
    
    # Save and retrieve during single session
    # example_save_and_retrieve_candidates()
    
    # Cross-task analysis (requires multiple previous runs)
    # example_cross_task_analysis()
    
    # Benchmark evaluation pattern
    # example_benchmark_evaluation()
    
    print("Import these functions to use in your workflow:")
    print("  - run_logistics_specialist(constraints_json, task_id)")
    print("  - run_activities_specialist(constraints_json, task_id)")
    print("  - retrieve_candidates(task_id, category=None)")
    print("  - list_candidate_tasks()")
