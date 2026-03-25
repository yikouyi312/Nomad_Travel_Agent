"""
Simple Evaluator Usage Examples

Demonstrates the simplified NomadEvaluator API that does NOT require task_file.
"""

from evaluator import NomadEvaluator

# =============================================================================
# Example 1: MINIMAL - Just evaluate a plan
# =============================================================================
print("=" * 70)
print("Example 1: Minimal - Just evaluate a plan")
print("=" * 70)

# Create evaluator (no task_file!)
evaluator = NomadEvaluator()

# Your verified plan
plan = {
    "task_id": "trip_001",
    "is_valid": True,
    "itinerary": {
        "trip_summary": {
            "destination": "Tokyo",
            "origin": "New York",
            "start_date": "2024-07-01",
            "end_date": "2024-07-08",
            "duration_nights": 7,
            "num_travelers": 1
        },
        "flights": {
            "outbound": {
                "airline": "JAL",
                "departure": "New York",
                "arrival_city": "Tokyo",
                "price_usd": 800
            },
            "return": {
                "airline": "JAL",
                "departure": "Tokyo",
                "arrival_city": "New York",
                "price_usd": 800
            }
        },
        "accommodation": {
            "name": "Shinjuku Hotel",
            "address": "Tokyo",
            "city": "Tokyo",
            "check_in_date": "2024-07-01",
            "check_out_date": "2024-07-08",
            "num_nights": 7,
            "price_per_night": 100,
            "total_nights_cost": 700
        },
        "activities": [],
        "cost_breakdown": {
            "total_estimated": 1500
        }
    }
}

# Evaluate - JUST PASS THE PLAN!
result = evaluator.evaluate(agent_output=plan)

print(f"\nResult:")
print(f"  Task ID: {result['task_id']}")
print(f"  Overall Score: {result['overall_score']:.1%}")
print(f"  Schema Valid: {result['itinerary_validity']}")

# =============================================================================
# Example 2: WITH CONSTRAINTS - Specify explicit constraints
# =============================================================================
print("\n" + "=" * 70)
print("Example 2: With Explicit Constraints")
print("=" * 70)

result = evaluator.evaluate(
    agent_output=plan,
    task_id="tokyo_trip_001",
    hard_constraints=[
        "Budget: $2000",
        "Destination: Tokyo",
        "Duration: 7 nights"
    ],
    expected_tools=["flight_search", "hotel_search"],
    tool_logs=[]
)

print(f"\nResult:")
print(f"  Overall Score: {result['overall_score']:.1%}")
print(f"  CSR Score: {result['csr_score']:.1%}")
print(f"  Constraint Breakdown:")
for constraint, met in result['constraint_breakdown'].items():
    status = "✓" if met else "✗"
    print(f"    {status} {constraint}")

# =============================================================================
# Example 3: AUTO-EXTRACT - Let evaluator infer constraints from plan
# =============================================================================
print("\n" + "=" * 70)
print("Example 3: Auto-Extract Constraints from Plan")
print("=" * 70)

# Don't pass hard_constraints - evaluator will extract from plan!
result = evaluator.evaluate(
    agent_output=plan,
    tool_logs=[]
)

print(f"\nResult (constraints auto-extracted):")
print(f"  Overall Score: {result['overall_score']:.1%}")
print(f"  Constraints inferred from plan:")
for constraint, met in result['constraint_breakdown'].items():
    print(f"    • {constraint}")

# =============================================================================
# Example 4: WITH TOOL LOGS - Track tool usage
# =============================================================================
print("\n" + "=" * 70)
print("Example 4: With Tool Logs")
print("=" * 70)

tool_logs = [
    {"tool": "flight_search", "params": {"origin": "New York", "destination": "Tokyo"}},
    {"tool": "hotel_search", "params": {"city": "Tokyo"}},
]

result = evaluator.evaluate(
    agent_output=plan,
    task_id="tokyo_trip_001",
    hard_constraints=["Destination: Tokyo"],
    expected_tools=["flight_search", "hotel_search", "activities_search"],
    tool_logs=tool_logs
)

print(f"\nResult (with tool tracking):")
print(f"  Tool Accuracy: {result['tool_accuracy']:.1%}")
print(f"  Overall Score: {result['overall_score']:.1%}")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 70)
print("API Summary")
print("=" * 70)
print("""
NomadEvaluator() - SIMPLIFIED API
==================================

No task_file required! Just pass the plan:

    evaluator = NomadEvaluator()  # No arguments!
    
    result = evaluator.evaluate(
        agent_output=plan_dict,      # REQUIRED: The plan to evaluate
        task_id="optional_id",       # Optional: For reference
        hard_constraints=[...],      # Optional: Explicit constraints
        expected_tools=[...],        # Optional: Expected tool calls
        tool_logs=[...]              # Optional: Track tool usage
    )

If hard_constraints not provided → auto-extracts from plan!
If expected_tools not provided → defaults to standard tools
If tool_logs not provided → uses empty list

Returns: Dictionary with scores and detailed breakdown
""")
