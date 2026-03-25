# Plan Scheme Integration Guide

## Quick Start

### 1. What is Plan Schema?

The **Plan Schema** is a standardized JSON structure that defines what a "valid" travel plan looks like. It ensures:
- ✓ All necessary information is present (flights, hotels, activities, costs)
- ✓ Data types and values are correct
- ✓ Plans can be compared fairly across benchmark tasks
- ✓ Evaluation metrics are consistent

### 2. For Verifier Agent

When returning a verified itinerary, follow this structure:

```python
# In verifier.py - modify verify_and_format_itinerary()

verified_result = {
    "task_id": task_id,
    "is_valid": all_hard_constraints_met,
    "status": "approved" if is_valid else "requires_revision",
    "itinerary": {
        "trip_summary": {
            "destination": destination_city,
            "origin": origin_city,
            "start_date": "YYYY-MM-DD",    # ISO format
            "end_date": "YYYY-MM-DD",
            "duration_nights": num_nights,
            "num_travelers": num_travelers
        },
        
        "flights": {
            "outbound": {
                "airline": airline_name,
                "flight_number": flight_num,
                "departure": departure_city,
                "departure_time": "HH:MM",
                "arrival_city": arrival_city,
                "arrival_time": "HH:MM",
                "duration": "12h 30m",
                "price_usd": float(price),
                "booking_reference": ref_num  # optional
            },
            "return": {
                # Same structure as outbound
            }
        },
        
        "accommodation": {
            "name": hotel_name,
            "address": address_str,
            "city": city_name,
            "check_in_date": "YYYY-MM-DD",
            "check_out_date": "YYYY-MM-DD",
            "num_nights": num_nights,
            "rating": float(rating),  # 0-5
            "price_per_night": float(price),
            "total_nights_cost": float(price) * num_nights,
            "room_type": room_type_str,
            "amenities": ["wifi", "gym", ...],
            "booking_reference": ref_num  # optional
        },
        
        "activities": [
            {
                "date": "YYYY-MM-DD",
                "day_number": 1,
                "name": activity_name,
                "type": "attraction|restaurant|tour|museum|entertainment|shopping|sports",
                "time": "HH:MM",
                "duration_hours": 2.5,
                "description": "...",
                "location": location_str,
                "price_per_person": float(price),
                "total_price": float(price) * num_travelers
            },
            # ... more activities
        ],
        
        "cost_breakdown": {
            "flights_outbound": float(outbound_price),
            "flights_return": float(return_price),
            "accommodation": float(hotel_total),
            "activities": sum_of_activities,
            "meals": estimated_or_included_in_activities,
            "transportation_local": estimated_local_transport,
            "miscellaneous": other_costs,
            "total_estimated": TOTAL_SUM  # Must match sum of above
        }
    },
    
    "constraint_validation": {
        "hard_constraints_met": ["list of satisfied constraints"],
        "hard_constraints_violated": ["list of violated constraints"],
        "csr_score": 0.0-1.0
    },
    
    "quality_metrics": {
        "price_optimality": 0.85,      # How close to best value
        "date_feasibility": 1.0,       # Timeline works
        "itinerary_coherence": 0.9,    # Activities flow logically
        "completeness_score": 0.95     # All required fields present
    }
}

return verified_result
```

### 3. For Evaluator

The Evaluator automatically validates plans:

```python
from evaluator import NomadEvaluator

# Initialize
evaluator = NomadEvaluator("data/tasks.json")

# Evaluate a plan
result = evaluator.evaluate(
    task_id="nomad_task_001",
    agent_output=verified_itinerary_dict,  # From Verifier
    tool_logs=list_of_tool_calls             # History of tool uses
)

# Result contains:
# - overall_score: 0-1 (weighted combination of metrics)
# - csr_score: Constraint satisfaction (35% weight)
# - schema_compliance: Format validity (25% weight)
# - tool_accuracy: Correct tools used (20% weight)
# - Conflict analysis: Temporal/spatial issues (20% weight)
```

### 4. Data Format Requirements

| Field | Format | Example | Rules |
|-------|--------|---------|-------|
| **Dates** | YYYY-MM-DD | "2024-07-15" | ISO 8601, must be valid |
| **Times** | HH:MM | "14:30" | 24-hour format |
| **Duration** | "Xh Ym" or float | "12h 30m" or 12.5 | Hours as decimal in calculations |
| **Price** | float | 125.50 | Positive, 2 decimals, USD |
| **Rating** | float | 4.5 | 0-5 range |
| **Count** | integer | 3 | Positive integers |

### 5. Common Integration Points

#### Point A: Specialist Phase (Search & Filter)
- **No schema needed here** - This phase produces search results
- Focus on finding multiple candidates

#### Point B: Verifier Phase (Decision & Formatting)
- **SCHEMA REQUIRED** - Must return Plan Schema format
- Select best combination from candidates
- Format all details according to schema
- Validate before returning

```python
# In verifier.py
from plan_schema import validate_plan

# Before returning:
validation = validate_plan(verified_itinerary)
if not validation['is_valid']:
    print(f"Schema errors: {validation['errors']}")
    # Fix issues before returning
```

#### Point C: Evaluation Phase (Scoring)
- **Schema used automatically** - Evaluator checks compliance
- Reports quality metrics
- Compares across benchmark tasks

### 6. Validation Checklist

Before Verifier returns a plan, verify:

- [ ] `task_id` matches the input task
- [ ] `itinerary.trip_summary` has all 6 fields
- [ ] `itinerary.flights` has outbound AND return
- [ ] Each flight has: airline, departure, arrival_city, price_usd
- [ ] `itinerary.accommodation` has: name, address, city, dates, prices
- [ ] `total_nights_cost` = `price_per_night` × `num_nights`
- [ ] All activities have date (within trip dates), name, type, price
- [ ] `cost_breakdown.total_estimated` = sum of all costs (with 10% tolerance)
- [ ] All dates are YYYY-MM-DD format
- [ ] All times are HH:MM format (24-hour)
- [ ] All prices are float ≥ 0
- [ ] Ratings are 0-5 range

### 7. Example Implementation

```python
# In verifier.py - Complete integration

from plan_schema import validate_plan

def verify_and_format_itinerary(self, ...):
    # ... existing verification logic ...
    
    # Build itinerary following schema
    verified_itinerary = {
        "task_id": self.task_id,
        "is_valid": constraints_satisfied,
        "status": "approved" if constraints_satisfied else "requires_revision",
        "itinerary": {
            "trip_summary": {
                "destination": best_destination,
                "origin": best_origin,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "duration_nights": (end_date - start_date).days,
                "num_travelers": num_travelers
            },
            "flights": {
                "outbound": {
                    "airline": outbound["airline"],
                    "flight_number": outbound.get("flight_number", ""),
                    "departure": outbound["departure"],
                    "departure_time": outbound.get("departure_time", ""),
                    "arrival_city": outbound["arrival_city"],
                    "arrival_time": outbound.get("arrival_time", ""),
                    "duration": outbound.get("duration", ""),
                    "price_usd": float(outbound["price"]),
                    "booking_reference": outbound.get("reference", "")
                },
                "return": {
                    # Similar structure
                }
            },
            "accommodation": {
                "name": hotel["name"],
                "address": hotel["address"],
                "city": hotel["city"],
                "check_in_date": check_in.strftime("%Y-%m-%d"),
                "check_out_date": check_out.strftime("%Y-%m-%d"),
                "num_nights": (check_out - check_in).days,
                "rating": float(hotel.get("rating", 0)),
                "price_per_night": float(hotel["price_per_night"]),
                "total_nights_cost": float(hotel["price_per_night"]) * (check_out - check_in).days,
                "room_type": hotel.get("room_type", ""),
                "amenities": hotel.get("amenities", []),
                "booking_reference": hotel.get("reference", "")
            },
            "activities": [
                {
                    "date": activity["date"],
                    "day_number": day_num,
                    "name": activity["name"],
                    "type": activity["type"],
                    "time": activity.get("time", ""),
                    "duration_hours": float(activity.get("duration", 0)),
                    "description": activity.get("description", ""),
                    "location": activity["location"],
                    "price_per_person": float(activity["price"]),
                    "total_price": float(activity["price"]) * num_travelers
                }
                for day_num, activity in enumerate(activities, 1)
            ],
            "cost_breakdown": {
                "flights_outbound": float(outbound_price),
                "flights_return": float(return_price),
                "accommodation": float(hotel_total),
                "activities": float(sum(a["price"] * num_travelers for a in activities)),
                "meals": 0.0,
                "transportation_local": 0.0,
                "miscellaneous": 0.0,
                "total_estimated": float(total_cost)
            }
        }
    }
    
    # Validate schema before returning
    validation = validate_plan(verified_itinerary)
    if not validation['is_valid']:
        self.logger.error(f"Schema validation failed: {validation['errors']}")
        # Fix or raise error
    
    return verified_itinerary
```

### 8. Troubleshooting

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| "missing_fields" errors | Schema validation fails | Ensure ALL required fields are populated (see PLAN_SCHEMA.md) |
| "Cost mismatch" warnings | Evaluator detects calculation error | Verify: total = outbound + return + hotel + activities + other |
| "has_conflicts: true" | Temporal/spatial issues detected | Check: flight times reasonable, hotel dates valid, activities within trip |
| "csr_score: 0.0" | No constraints satisfied | Check constraint parsing in evaluator._check_constraints() |
| "tool_accuracy" low | Wrong tools or hallucination | Ensure tool_logs contain only: flight_search, hotel_search, activities_search |

### 9. Testing Your Integration

```bash
# Run schema validation tests
python nomad/src/tools/test_plan_schema.py

# Output should show:
# - TEST 1: Valid Plan Validation ✓
# - TEST 2: Missing Required Fields ✓
# - TEST 3: Date/Time Conflicts Detection ✓
# - TEST 4: Cost Calculation Verification ✓
# - ALL TESTS PASSED ✓
```

### 10. Next Steps

After implementing Plan Schema:

1. ✓ Verifier returns Schema-compliant output
2. ✓ Test with sample tasks
3. ✓ Run Evaluator to get scoring
4. ✓ Identify and fix schema compliance issues
5. ✓ Benchmark all tasks
6. ✓ Analyze scoring distribution
7. ✓ Iterate agent improvements based on metrics

---

**Questions?** Refer to:
- `PLAN_SCHEMA.md` — Complete schema documentation
- `test_plan_schema.py` — Working examples
- `evaluator.py` — Evaluation logic
