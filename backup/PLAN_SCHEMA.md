# Standard Plan Schema for Nomad Agent Evaluation

## Overview

The **Plan Schema** defines the canonical structure for all `verified_itinerary` outputs from the Verifier agent. This schema enables standardized evaluation, comparison, and validation of travel plans across all benchmark tasks.

## Schema Hierarchy

```
Plan
├── task_id: str
├── is_valid: bool
├── status: enum(approved|requires_revision|invalid)
└── itinerary
    ├── trip_summary
    │   ├── destination: str
    │   ├── origin: str
    │   ├── start_date: YYYY-MM-DD
    │   ├── end_date: YYYY-MM-DD
    │   ├── duration_nights: int
    │   └── num_travelers: int
    │
    ├── flights
    │   ├── outbound: FlightSegment
    │   │   ├── airline: str
    │   │   ├── flight_number: str
    │   │   ├── departure: str (origin city)
    │   │   ├── departure_time: str (HH:MM)
    │   │   ├── arrival_city: str
    │   │   ├── arrival_time: str (HH:MM)
    │   │   ├── duration: str (e.g., "12h 30m")
    │   │   ├── price_usd: float
    │   │   └── booking_reference: str (optional)
    │   │
    │   └── return: FlightSegment (same as outbound)
    │
    ├── accommodation
    │   ├── name: str
    │   ├── address: str
    │   ├── city: str
    │   ├── check_in_date: YYYY-MM-DD
    │   ├── check_out_date: YYYY-MM-DD
    │   ├── num_nights: int
    │   ├── rating: float (0-5)
    │   ├── price_per_night: float
    │   ├── total_nights_cost: float
    │   ├── room_type: str
    │   ├── amenities: [str]
    │   └── booking_reference: str (optional)
    │
    ├── activities: [{
    │   ├── date: YYYY-MM-DD
    │   ├── day_number: int
    │   ├── name: str
    │   ├── type: enum(attraction|restaurant|tour|museum|entertainment|shopping|sports)
    │   ├── time: str (HH:MM or time_range)
    │   ├── duration_hours: float
    │   ├── description: str
    │   ├── location: str
    │   ├── price_per_person: float
    │   ├── total_price: float (price_per_person × num_travelers)
    │   └── booking_reference: str (optional)
    │ }]
    │
    └── cost_breakdown
        ├── flights_outbound: float
        ├── flights_return: float
        ├── accommodation: float
        ├── activities: float
        ├── meals: float (estimated if not in activities)
        ├── transportation_local: float
        ├── miscellaneous: float
        └── total_estimated: float
```

## Required vs Optional Fields

### REQUIRED (Plan will fail validation without these):
- `task_id` — links plan to benchmark task
- `is_valid` — boolean indicating constraint compliance
- `itinerary.trip_summary` — must include destination, origin, start_date, end_date, duration_nights
- `itinerary.flights.outbound` — must include airline, departure, arrival_city, price_usd
- `itinerary.flights.return` — same requirements as outbound
- `itinerary.accommodation` — must include name, address, city, check_in/check_out, price_per_night, total_nights_cost
- `itinerary.cost_breakdown.total_estimated` — total cost calculation

### OPTIONAL (Plan can include for richer evaluation):
- `booking_reference` — confirmation numbers
- `flight_number`, `duration` — flight details
- `amenities` — hotel features
- `activity descriptions` — more context on activities
- `meals` cost — can be part of activities or estimated

## Data Type Specifications

| Field | Type | Example | Validation |
|-------|------|---------|-----------|
| date | YYYY-MM-DD | "2024-07-15" | ISO 8601 format |
| time | HH:MM | "14:30" or "2:30 PM" | 24-hour or 12-hour with AM/PM |
| duration | str or float | "12h 30m" or 12.5 | hours as float or "Xh Ym" format |
| price | float | 125.50 | Greater than 0, rounded to 2 decimals |
| rating | float | 4.5 | 0-5 range |
| nights | int | 3 | Integer >= 1 |

## Evaluation Metrics

The `NomadEvaluator` uses the schema to calculate:

1. **Schema Compliance (25%)** — Does the output match PLAN_SCHEMA?
   - All required fields present
   - Correct data types
   - Valid value ranges

2. **Constraint Satisfaction Rate - CSR (35%)** — Does plan meet task requirements?
   - Budget constraints
   - Destination/origin requirements
   - Duration requirements
   - Dietary/preference constraints
   - Hotel rating minimums

3. **Tool Accuracy (20%)** — Were appropriate tools used?
   - Search, hotel_search, activities_search tools called
   - No hallucinated tools
   - Tools called with valid parameters

4. **Itinerary Consistency (20%)** — Are there conflicts?
   - Flight times are reasonable
   - Hotel dates are valid
   - Activities fall within trip dates
   - Cost calculations are accurate (within 10% tolerance)
   - No temporal overlaps

## Overall Score Calculation

```
Overall Score = 
    (Schema Compliance * 0.25) +
    (CSR * 0.35) +
    (Tool Accuracy * 0.20) +
    (Has No Conflicts ? 1.0 : 0.5) * 0.20
```

Result ranges: **0.0 to 1.0** (1.0 = perfect plan)

## Usage Example

### Sample Plan Output (Verifier)
```json
{
  "task_id": "nomad_task_001",
  "is_valid": true,
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
        "arrival_time": "06:00",
        "duration": "7h 45m",
        "price_usd": 450,
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
        "price_usd": 420,
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
      "price_per_night": 120,
      "total_nights_cost": 840,
      "room_type": "Deluxe Double",
      "amenities": ["wi-fi", "gym", "breakfast", "concierge"],
      "booking_reference": "HLM-789456"
    },
    "activities": [
      {
        "date": "2024-07-15",
        "day_number": 1,
        "name": "Arrival & Rest",
        "type": "accommodation",
        "time": "18:00",
        "duration_hours": 0,
        "location": "Hotel Le Marais",
        "price_per_person": 0,
        "total_price": 0
      },
      {
        "date": "2024-07-16",
        "day_number": 2,
        "name": "Eiffel Tower Tour",
        "type": "attraction",
        "time": "09:00",
        "duration_hours": 2.5,
        "description": "Skip-the-line guided tour of Eiffel Tower",
        "location": "Eiffel Tower, Paris",
        "price_per_person": 35,
        "total_price": 70
      },
      {
        "date": "2024-07-16",
        "day_number": 2,
        "name": "Lunch at Jules Verne",
        "type": "restaurant",
        "time": "13:00",
        "duration_hours": 1.5,
        "location": "Jules Verne Restaurant, Paris",
        "price_per_person": 80,
        "total_price": 160
      }
    ],
    "cost_breakdown": {
      "flights_outbound": 450,
      "flights_return": 420,
      "accommodation": 840,
      "activities": 230,
      "meals": 400,
      "transportation_local": 60,
      "miscellaneous": 0,
      "total_estimated": 2400
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
```

### Evaluating This Plan

```python
from evaluator import NomadEvaluator

evaluator = NomadEvaluator("data/tasks.json")
result = evaluator.evaluate(
    task_id="nomad_task_001",
    agent_output=plan,  # The plan above
    tool_logs=[...]  # Record of tool calls
)

print(result)
# Output:
# {
#   "task_id": "nomad_task_001",
#   "overall_score": 0.92,
#   "csr_score": 1.0,
#   "tool_accuracy": 0.95,
#   "schema_compliance": 0.95,
#   "itinerary_validity": true,
#   "constraint_breakdown": {"Budget: $3000": true, "Destination: Paris": true, ...}
# }
```

## Integration with Verifier

The Verifier agent should output data in this schema format. Example integration:

```python
# In verifier.py
verified_itinerary = {
    "task_id": task_id,
    "is_valid": all_constraints_met,
    "status": "approved" if is_valid else "requires_revision",
    "itinerary": {
        "trip_summary": {
            "destination": candidate_destination,
            "origin": origin,
            # ... populated from top candidates
        },
        "flights": selected_flights,
        "accommodation": selected_hotel,
        "activities": selected_activities,
        "cost_breakdown": calculate_costs(flights, hotel, activities)
    },
    "constraint_validation": constraint_check_result
}

return verified_itinerary
```

## Common Validation Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Missing required fields | Incomplete itinerary building | Ensure all required fields populated before returning |
| Cost mismatch errors | Math errors in total_estimated | Verify: sum(flights) + hotel + activities + misc = total |
| Date conflicts | Activities outside trip window | Validate all activity dates ∈ [check_in, check_out] |
| Invalid dates | Wrong date format | Use ISO 8601: YYYY-MM-DD |
| Price validation fails | Negative prices or zeros | All prices must be ≥ 0 |
| CSR score low | Constraints not extracted correctly | Check constraint parsing in _check_constraints() |

## Testing the Schema

```python
from plan_schema import validate_plan, format_plan_summary

# Basic validation
validation_result = validate_plan(my_plan)
print(f"Valid: {validation_result['is_valid']}")
print(f"Errors: {validation_result['errors']}")
print(f"Missing: {validation_result['missing_fields']}")

# Generate summary
summary = format_plan_summary(my_plan)
print(summary)
```

## Future Enhancements

- Add LLM-as-a-Judge for constraint interpretation
- Support multi-city itineraries with intermediate flights
- Include carbon footprint calculations
- Support group split-cost tracking
- Add weather compatibility checks
- Support activity preference scoring
