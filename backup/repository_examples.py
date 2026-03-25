"""
Complete Example: Save & Evaluate Plans with Repository

This demonstrates the full workflow:
1. (Notebook) Generate and save plan
2. (Script) Load and evaluate by task_id
3. (Script) Batch evaluate all plans
4. (Script) Export summary
"""

from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator


def example_1_evaluate_single_plan():
    """Example 1: Load and evaluate a single plan by task_id"""
    print("\n" + "="*70)
    print("Example 1: Evaluate Single Plan by task_id")
    print("="*70)
    
    repo = PlanRepository()
    evaluator = NomadEvaluator()
    
    # First, check what plans we have
    all_plans = repo.get_all_plans()
    print(f"\nSaved plans: {all_plans}")
    
    if not all_plans:
        print("No plans saved yet! Run the notebook first.")
        return
    
    # Evaluate first plan
    task_id = all_plans[0]
    print(f"\n[Evaluating] {task_id}")
    
    result = evaluator.evaluate_from_repo(
        task_id=task_id
    )
    
    print(f"\nResult:")
    print(f"  Overall Score: {result['overall_score']:.1%}")
    print(f"  Schema Valid: {result['itinerary_validity']}")
    print(f"  CSR (Constraints): {result['csr_score']:.1%}")
    print(f"  Tool Accuracy: {result['tool_accuracy']:.1%}")


def example_2_batch_evaluate():
    """Example 2: Batch evaluate all saved plans"""
    print("\n" + "="*70)
    print("Example 2: Batch Evaluate All Plans")
    print("="*70)
    
    repo = PlanRepository()
    evaluator = NomadEvaluator()
    
    all_plans = repo.get_all_plans()
    print(f"\nEvaluating {len(all_plans)} plans...")
    
    results = {}
    for i, task_id in enumerate(all_plans, 1):
        print(f"  [{i}/{len(all_plans)}] {task_id}...", end=" ", flush=True)
        try:
            result = evaluator.evaluate_from_repo(task_id=task_id)
            results[task_id] = result
            print(f"✓ {result['overall_score']:.1%}")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Summary
    print(f"\n[BATCH RESULTS SUMMARY]")
    print(f"  Total evaluated: {len(results)}")
    if results:
        scores = [r['overall_score'] for r in results.values()]
        print(f"  Average score: {sum(scores)/len(scores):.1%}")
        print(f"  Best: {max(scores):.1%}")
        print(f"  Worst: {min(scores):.1%}")
        
        print(f"\n[Individual Scores]")
        for task_id, result in sorted(results.items()):
            print(f"  {task_id}: {result['overall_score']:.1%}")


def example_3_export_summary():
    """Example 3: Export summary of all plans"""
    print("\n" + "="*70)
    print("Example 3: Export Plans Summary")
    print("="*70)
    
    repo = PlanRepository()
    
    # Export summary
    summary_file = repo.export_plans_summary("plans_summary.json")
    
    print(f"\n✓ Summary exported to: {summary_file}")
    
    # Show contents
    import json
    with open(summary_file, "r") as f:
        summary = json.load(f)
    
    print(f"\nSummary Contents:")
    print(f"  Generated: {summary['generated_at']}")
    print(f"  Total plans: {summary['total_plans']}")
    print(f"\nPlans:")
    for task_id, plan_info in summary['plans'].items():
        print(f"\n  {task_id}:")
        print(f"    Destination: {plan_info['destination']}")
        print(f"    Origin: {plan_info['origin']}")
        print(f"    Duration: {plan_info['duration_nights']} nights")
        print(f"    Cost: ${plan_info['total_cost']:.2f}")
        print(f"    Valid: {'✓' if plan_info['is_valid'] else '✗'}")


def example_4_custom_evaluation():
    """Example 4: Evaluate with custom constraints"""
    print("\n" + "="*70)
    print("Example 4: Custom Evaluation with Specific Constraints")
    print("="*70)
    
    repo = PlanRepository()
    evaluator = NomadEvaluator()
    
    all_plans = repo.get_all_plans()
    if not all_plans:
        print("No plans saved yet!")
        return
    
    task_id = all_plans[0]
    print(f"\nEvaluating {task_id} with custom constraints...")
    
    # Evaluate with specific constraints
    result = evaluator.evaluate_from_repo(
        task_id=task_id,
        hard_constraints=[
            "Budget: $5000",
            "Destination: Tokyo",
            "Duration: 5 nights"
        ],
        expected_tools=["flight_search", "hotel_search"]
    )
    
    print(f"\nConstraint Breakdown:")
    for constraint, met in result['constraint_breakdown'].items():
        status = "✓" if met else "✗"
        print(f"  {status} {constraint}")
    
    print(f"\nScore: {result['overall_score']:.1%}")


def example_5_load_and_inspect():
    """Example 5: Load plan and inspect contents"""
    print("\n" + "="*70)
    print("Example 5: Load and Inspect Plan Details")
    print("="*70)
    
    repo = PlanRepository()
    
    all_plans = repo.get_all_plans()
    if not all_plans:
        print("No plans saved yet!")
        return
    
    task_id = all_plans[0]
    
    # Load with metadata
    data = repo.load_plan_with_metadata(task_id)
    plan = data['plan']
    metadata = data['metadata']
    
    print(f"\n[Metadata]")
    print(f"  Task ID: {metadata['task_id']}")
    print(f"  Saved: {metadata['saved_at']}")
    print(f"  Schema: {metadata['schema_version']}")
    
    itinerary = plan.get('itinerary', {})
    trip = itinerary.get('trip_summary', {})
    flights = itinerary.get('flights', {})
    accommodation = itinerary.get('accommodation', {})
    
    print(f"\n[Trip Details]")
    print(f"  From: {trip.get('origin')}")
    print(f"  To: {trip.get('destination')}")
    print(f"  Dates: {trip.get('start_date')} to {trip.get('end_date')}")
    print(f"  Duration: {trip.get('duration_nights')} nights")
    
    print(f"\n[Flights]")
    outbound = flights.get('outbound', {})
    return_flight = flights.get('return', {})
    print(f"  Outbound: {outbound.get('airline')} - ${outbound.get('price_usd')}")
    print(f"  Return: {return_flight.get('airline')} - ${return_flight.get('price_usd')}")
    
    print(f"\n[Accommodation]")
    print(f"  Hotel: {accommodation.get('name')}")
    print(f"  Check-in: {accommodation.get('check_in_date')}")
    print(f"  Check-out: {accommodation.get('check_out_date')}")
    print(f"  Price: ${accommodation.get('total_nights_cost')}")
    
    cost = itinerary.get('cost_breakdown', {})
    print(f"\n[Cost Breakdown]")
    print(f"  Total: ${cost.get('total_estimated')}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("PLAN REPOSITORY & EVALUATION EXAMPLES")
    print("="*70)
    
    example_1_evaluate_single_plan()
    example_2_batch_evaluate()
    example_3_export_summary()
    example_4_custom_evaluation()
    example_5_load_and_inspect()
    
    print("\n" + "="*70)
    print("Examples completed!")
    print("="*70)


if __name__ == "__main__":
    main()
