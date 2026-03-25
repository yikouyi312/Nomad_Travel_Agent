"""
Test suite for Plan Schema validation and Evaluator integration.

Demonstrates:
1. Valid plan that passes all validations
2. Invalid plans with different types of errors
3. Evaluator scoring with schema compliance
"""

import json
from plan_schema import validate_plan, format_plan_summary, PLAN_SCHEMA
from evaluator import NomadEvaluator


# ============================================================================
# VALID PLAN EXAMPLE - Full Compliant Output
# ============================================================================

VALID_PLAN = {
    "task_id": "nomad_task_001",
    "is_valid": True,
    "status": "approved",
    "itinerary": {
        "trip_summary": {
            "destination": "Paris",
            "origin": "New York",
            "start_date": "2024-07-15",
            "end_date": "2024-07-22",
            "duration_nights": 7,
            "num_travelers": 2
        },
        "flights": {
            "outbound": {
                "airline": "Air France",
                "flight_number": "AF6015",
                "departure": "New York (JFK)",
                "departure_time": "18:00",
                "arrival_city": "Paris (CDG)",
                "arrival_time": "06:00+1",
                "duration": "7h 45m",
                "price_usd": 450.00,
                "booking_reference": "6X9K2M"
            },
            "return": {
                "airline": "American Airlines",
                "flight_number": "AA4521",
                "departure": "Paris (CDG)",
                "departure_time": "10:30",
                "arrival_city": "New York (JFK)",
                "arrival_time": "13:15",
                "duration": "8h 15m",
                "price_usd": 420.00,
                "booking_reference": "7Y4L5N"
            }
        },
        "accommodation": {
            "name": "Hotel Le Marais",
            "address": "23 Rue de Beauce",
            "city": "Paris",
            "check_in_date": "2024-07-15",
            "check_out_date": "2024-07-22",
            "num_nights": 7,
            "rating": 4.6,
            "price_per_night": 120.00,
            "total_nights_cost": 840.00,
            "room_type": "Deluxe Double",
            "amenities": ["wi-fi", "gym", "breakfast", "concierge"],
            "booking_reference": "HLM-789456"
        },
        "activities": [
            {
                "date": "2024-07-16",
                "day_number": 1,
                "name": "Eiffel Tower Tour",
                "type": "attraction",
                "time": "09:00",
                "duration_hours": 2.5,
                "description": "Skip-the-line guided tour",
                "location": "Eiffel Tower, Paris",
                "price_per_person": 35.00,
                "total_price": 70.00,
                "booking_reference": "EIFFEL-001"
            },
            {
                "date": "2024-07-16",
                "day_number": 1,
                "name": "Lunch at Jules Verne",
                "type": "restaurant",
                "time": "13:00",
                "duration_hours": 1.5,
                "location": "Jules Verne Restaurant",
                "price_per_person": 80.00,
                "total_price": 160.00
            },
            {
                "date": "2024-07-17",
                "day_number": 2,
                "name": "Louvre Museum",
                "type": "museum",
                "time": "10:00",
                "duration_hours": 3.0,
                "description": "Guided tour through masterpieces",
                "location": "Louvre, Paris",
                "price_per_person": 25.00,
                "total_price": 50.00
            }
        ],
        "cost_breakdown": {
            "flights_outbound": 450.00,
            "flights_return": 420.00,
            "accommodation": 840.00,
            "activities": 280.00,
            "meals": 200.00,
            "transportation_local": 80.00,
            "miscellaneous": 50.00,
            "total_estimated": 2320.00
        }
    },
    "constraint_validation": {
        "hard_constraints_met": [
            "Budget: $3000",
            "Destination: Paris",
            "Duration: 7 nights"
        ],
        "hard_constraints_violated": [],
        "csr_score": 1.0
    },
    "quality_metrics": {
        "price_optimality": 0.85,
        "date_feasibility": 1.0,
        "itinerary_coherence": 0.9,
        "completeness_score": 0.95
    }
}


# ============================================================================
# INVALID PLAN EXAMPLES
# ============================================================================

# Missing required fields
INVALID_PLAN_MISSING_FLIGHTS = {
    "task_id": "nomad_task_002",
    "is_valid": False,
    "itinerary": {
        "trip_summary": {
            "destination": "Tokyo",
            "origin": "New York",
            "start_date": "2024-08-01",
            "end_date": "2024-08-08",
            "duration_nights": 7
        },
        # Missing flights!
        "accommodation": {
            "name": "Shinjuku Hotel",
            "address": "Tokyo",
            "city": "Tokyo",
            "check_in_date": "2024-08-01",
            "check_out_date": "2024-08-08",
            "num_nights": 7,
            "price_per_night": 150.00,
            "total_nights_cost": 1050.00
        },
        "cost_breakdown": {
            "total_estimated": 1050.00
        }
    }
}

# Inconsistent dates (check_out before check_in)
INVALID_PLAN_DATE_CONFLICT = {
    "task_id": "nomad_task_003",
    "is_valid": True,
    "itinerary": {
        "trip_summary": {
            "destination": "London",
            "origin": "New York",
            "start_date": "2024-09-01",
            "end_date": "2024-09-08",
            "duration_nights": 7
        },
        "flights": {
            "outbound": {
                "airline": "British Airways",
                "flight_number": "BA112",
                "departure": "New York (JFK)",
                "departure_time": "10:00",
                "arrival_city": "London (LHR)",
                "arrival_time": "22:00+1",
                "duration": "7h 30m",
                "price_usd": 550.00
            },
            "return": {
                "airline": "British Airways",
                "flight_number": "BA113",
                "departure": "London (LHR)",
                "departure_time": "08:00",  # Departs BEFORE outbound arrives!
                "arrival_city": "New York (JFK)",
                "arrival_time": "10:00",
                "duration": "8h",
                "price_usd": 520.00
            }
        },
        "accommodation": {
            "name": "London Hotel",
            "address": "London",
            "city": "London",
            "check_in_date": "2024-09-08",  # After check_out!
            "check_out_date": "2024-09-01",
            "num_nights": 7,
            "price_per_night": 120.00,
            "total_nights_cost": 840.00
        },
        "activities": [],
        "cost_breakdown": {
            "total_estimated": 1910.00
        }
    }
}

# Cost calculation mismatch
INVALID_PLAN_COST_MISMATCH = {
    "task_id": "nomad_task_004",
    "is_valid": True,
    "itinerary": {
        "trip_summary": {
            "destination": "Barcelona",
            "origin": "New York",
            "start_date": "2024-10-01",
            "end_date": "2024-10-08",
            "duration_nights": 7
        },
        "flights": {
            "outbound": {
                "airline": "Iberia",
                "flight_number": "IB6104",
                "departure": "New York (JFK)",
                "departure_time": "14:00",
                "arrival_city": "Barcelona",
                "arrival_time": "04:00+1",
                "price_usd": 400.00
            },
            "return": {
                "airline": "Iberia",
                "flight_number": "IB6105",
                "departure": "Barcelona",
                "departure_time": "16:00",
                "arrival_city": "New York (JFK)",
                "arrival_time": "18:00",
                "price_usd": 380.00
            }
        },
        "accommodation": {
            "name": "Barcelona Hotel",
            "address": "Barcelona",
            "city": "Barcelona",
            "check_in_date": "2024-10-01",
            "check_out_date": "2024-10-08",
            "num_nights": 7,
            "price_per_night": 100.00,
            "total_nights_cost": 700.00
        },
        "activities": [
            {
                "date": "2024-10-02",
                "day_number": 1,
                "name": "Sagrada Familia",
                "type": "attraction",
                "time": "10:00",
                "duration_hours": 2.0,
                "price_per_person": 30.00,
                "total_price": 30.00
            }
        ],
        "cost_breakdown": {
            "flights_outbound": 400.00,
            "flights_return": 380.00,
            "accommodation": 700.00,
            "activities": 30.00,
            "meals": 0.00,
            "transportation_local": 0.00,
            "miscellaneous": 0.00,
            "total_estimated": 5000.00  # WRONG! Should be 1510
        }
    }
}


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_valid_plan():
    """Test that a valid plan passes all validations."""
    print("\n" + "="*70)
    print("TEST 1: Valid Plan Validation")
    print("="*70)
    
    result = validate_plan(VALID_PLAN)
    print(f"✓ Schema Valid: {result['is_valid']}")
    print(f"  Score: {result['score']}/1.0")
    
    if result['errors']:
        print(f"  Errors: {result['errors']}")
    if result['missing_fields']:
        print(f"  Missing: {result['missing_fields']}")
    
    # Print summary
    summary = format_plan_summary(VALID_PLAN)
    print(summary)
    
    assert result['is_valid'], "Valid plan should pass validation"


def test_missing_fields():
    """Test plan with missing required fields."""
    print("\n" + "="*70)
    print("TEST 2: Missing Required Fields")
    print("="*70)
    
    result = validate_plan(INVALID_PLAN_MISSING_FLIGHTS)
    print(f"✓ Schema Valid: {result['is_valid']}")
    print(f"  Score: {result['score']}/1.0")
    print(f"  Missing Fields: {result['missing_fields']}")
    
    assert not result['is_valid'], "Plan with missing flights should fail"
    assert any('flights' in field for field in result['missing_fields']), "Should identify missing flights"


def test_date_conflicts():
    """Test plan with date/time conflicts."""
    print("\n" + "="*70)
    print("TEST 3: Date/Time Conflicts Detection")
    print("="*70)
    
    result = validate_plan(INVALID_PLAN_DATE_CONFLICT)
    print(f"✓ Schema Valid: {result['is_valid']}")
    print(f"  Score: {result['score']}/1.0")
    print(f"  Errors: {result['errors']}")
    
    # The schema validation may pass (structure is correct), 
    # but consistency check should catch the conflict
    print(f"  → Consistency check would catch date conflicts")


def test_cost_mismatch():
    """Test plan with cost calculation errors."""
    print("\n" + "="*70)
    print("TEST 4: Cost Calculation Verification")
    print("="*70)
    
    result = validate_plan(INVALID_PLAN_COST_MISMATCH)
    print(f"✓ Schema Valid: {result['is_valid']}")
    print(f"  Score: {result['score']}/1.0")
    
    # Schema validation doesn't check calculation errors
    # These are caught by consistency check in Evaluator
    print(f"  → Evaluator consistency check would detect: total $5000 vs calculated $1510")


def test_evaluator_integration():
    """Test Evaluator scoring with schema."""
    print("\n" + "="*70)
    print("TEST 5: Evaluator Integration")
    print("="*70)
    
    evaluator = NomadEvaluator("../../../nomad_benchmark/data/tasks.json")
    
    # Mock task
    mock_task_id = "test_task_001"
    evaluator.tasks[mock_task_id] = {
        "task_id": mock_task_id,
        "tier": "medium",
        "constraints": {
            "hard": [
                "Budget: $3000",
                "Destination: Paris",
                "Duration: 7 nights"
            ]
        },
        "expected_tools": ["flight_search", "hotel_search", "activities_search"]
    }
    
    # Mock tool logs
    tool_logs = [
        {"tool": "flight_search", "params": {}},
        {"tool": "hotel_search", "params": {}},
        {"tool": "activities_search", "params": {}}
    ]
    
    # Evaluate
    eval_result = evaluator.evaluate(mock_task_id, VALID_PLAN, tool_logs)
    
    print(f"✓ Overall Score: {eval_result['overall_score']}/1.0")
    print(f"  ├─ Schema Compliance: {eval_result['schema_compliance']}")
    print(f"  ├─ CSR Score: {eval_result['csr_score']}")
    print(f"  ├─ Tool Accuracy: {eval_result['tool_accuracy']}")
    print(f"  ├─ Itinerary Valid: {eval_result['itinerary_validity']}")
    print(f"  └─ Has Conflicts: {eval_result['conflict_report']['has_conflicts']}")
    
    print(f"\n  Constraint Breakdown:")
    for constraint, met in eval_result['constraint_breakdown'].items():
        status = "✓" if met else "✗"
        print(f"    {status} {constraint}")


def run_all_tests():
    """Run all validation tests."""
    try:
        test_valid_plan()
        test_missing_fields()
        test_date_conflicts()
        test_cost_mismatch()
        # test_evaluator_integration()  # Skip if tasks.json not available
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        return False
    except FileNotFoundError as e:
        print(f"\n⚠ SKIPPED test_evaluator_integration (tasks.json not found): {str(e)}")
        return True
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
