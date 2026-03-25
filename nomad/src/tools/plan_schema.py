"""
Standard Travel Plan Schema for Nomad Agent

Defines the canonical structure for validated itineraries that evaluator can assess.
"""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "Unique task identifier"
        },
        "is_valid": {
            "type": "boolean",
            "description": "Whether plan meets all hard constraints"
        },
        "status": {
            "type": "string",
            "enum": ["approved", "requires_revision", "invalid"],
            "description": "Plan status"
        },
        "itinerary": {
            "type": "object",
            "description": "Complete confirmed travel plan",
            "properties": {
                "trip_summary": {
                    "type": "object",
                    "description": "Trip overview",
                    "properties": {
                        "destination": {"type": "string"},
                        "origin": {"type": "string"},
                        "start_date": {"type": "string", "format": "date"},
                        "end_date": {"type": "string", "format": "date"},
                        "duration_nights": {"type": "integer"},
                        "num_travelers": {"type": "integer"}
                    },
                    "required": ["destination", "origin", "start_date", "end_date", "duration_nights"]
                },
                "flights": {
                    "type": "object",
                    "description": "Flight bookings",
                    "properties": {
                        "outbound": {
                            "type": "object",
                            "properties": {
                                "airline": {"type": "string"},
                                "flight_number": {"type": "string"},
                                "departure": {"type": "string"},
                                "departure_time": {"type": "string"},
                                "arrival_city": {"type": "string"},
                                "arrival_time": {"type": "string"},
                                "duration": {"type": "string"},
                                "price_usd": {"type": "number"},
                                "booking_reference": {"type": "string"}
                            },
                            "required": ["airline", "departure", "arrival_city", "price_usd"]
                        },
                        "return": {
                            "type": "object",
                            "properties": {
                                "airline": {"type": "string"},
                                "flight_number": {"type": "string"},
                                "departure": {"type": "string"},
                                "departure_time": {"type": "string"},
                                "arrival_city": {"type": "string"},
                                "arrival_time": {"type": "string"},
                                "duration": {"type": "string"},
                                "price_usd": {"type": "number"},
                                "booking_reference": {"type": "string"}
                            },
                            "required": ["airline", "departure", "arrival_city", "price_usd"]
                        }
                    },
                    "required": ["outbound", "return"]
                },
                "accommodation": {
                    "type": "object",
                    "description": "Hotel accommodation",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {"type": "string"},
                        "city": {"type": "string"},
                        "check_in_date": {"type": "string", "format": "date"},
                        "check_out_date": {"type": "string", "format": "date"},
                        "num_nights": {"type": "integer"},
                        "rating": {"type": "number", "minimum": 0, "maximum": 5},
                        "price_per_night": {"type": "number"},
                        "total_nights_cost": {"type": "number"},
                        "room_type": {"type": "string"},
                        "amenities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "examples": ["wifi", "gym", "breakfast", "parking"]
                        },
                        "booking_reference": {"type": "string"}
                    },
                    "required": ["name", "address", "city", "check_in_date", "check_out_date", "price_per_night", "total_nights_cost"]
                },
                "activities": {
                    "type": "array",
                    "description": "Planned activities and dining",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "format": "date"},
                            "day_number": {"type": "integer"},
                            "name": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["attraction", "restaurant", "tour", "museum", "entertainment", "shopping", "sports"]
                            },
                            "time": {"type": "string"},
                            "duration_hours": {"type": "number"},
                            "description": {"type": "string"},
                            "location": {"type": "string"},
                            "price_per_person": {"type": "number"},
                            "total_price": {"type": "number"},
                            "booking_reference": {"type": "string"}
                        },
                        "required": ["date", "name", "type", "price_per_person"]
                    }
                },
                "cost_breakdown": {
                    "type": "object",
                    "description": "Itemized costs",
                    "properties": {
                        "flights_outbound": {"type": "number"},
                        "flights_return": {"type": "number"},
                        "accommodation": {"type": "number"},
                        "activities": {"type": "number"},
                        "meals": {"type": "number"},
                        "transportation_local": {"type": "number"},
                        "miscellaneous": {"type": "number"},
                        "total_estimated": {"type": "number"}
                    },
                    "required": ["total_estimated"]
                }
            },
            "required": ["trip_summary", "flights", "accommodation", "cost_breakdown"]
        },
        "constraint_validation": {
            "type": "object",
            "description": "Constraint satisfaction details",
            "properties": {
                "hard_constraints_met": {"type": "array", "items": {"type": "string"}},
                "hard_constraints_violated": {"type": "array", "items": {"type": "string"}},
                "soft_preferences_met": {"type": "array", "items": {"type": "string"}},
                "csr_score": {
                    "type": "number",
                    "description": "Constraint Satisfaction Rate (0-1)"
                }
            }
        },
        "quality_metrics": {
            "type": "object",
            "description": "Plan quality assessment",
            "properties": {
                "price_optimality": {
                    "type": "number",
                    "description": "How close to best value (0-1)"
                },
                "date_feasibility": {
                    "type": "number",
                    "description": "Dates match constraints (0-1)"
                },
                "itinerary_coherence": {
                    "type": "number",
                    "description": "Activities flow logically (0-1)"
                },
                "completeness_score": {
                    "type": "number",
                    "description": "All required elements present (0-1)"
                }
            }
        },
        "verification_notes": {
            "type": "string",
            "description": "Human-readable explanation of plan validity"
        }
    },
    "required": ["task_id", "is_valid", "itinerary", "constraint_validation"]
}


def validate_plan(plan: dict) -> dict:
    """
    Validates a plan against the schema.
    Handles both verification output format and PLAN_SCHEMA format.
    
    Args:
        plan: Plan dict to validate
    
    Returns:
        {
            "is_valid": bool,
            "errors": [error messages],
            "missing_fields": [field names],
            "score": float (0-1)
        }
    """
    errors = []
    missing_fields = []
    total_checks = 0
    passed_checks = 0

    # Get itinerary (could be nested under "itinerary" key, or the plan itself)
    itinerary = plan.get("itinerary", plan) if isinstance(plan, dict) else {}

    # 1. Check for flights
    total_checks += 1
    flights = itinerary.get("flights", {})
    if flights and (flights.get("outbound") or flights.get("return")):
        passed_checks += 1
    else:
        missing_fields.append("flights")

    # 2. Check for accommodation (hotels or accommodation)
    total_checks += 1
    hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
    if hotel and hotel.get("name"):
        passed_checks += 1
    else:
        missing_fields.append("accommodation")

    # 3. Check for activities
    total_checks += 1
    activities = itinerary.get("activities", [])
    if activities:
        passed_checks += 1
    else:
        missing_fields.append("activities")

    # 4. Check for cost info
    total_checks += 1
    has_cost = (
        itinerary.get("estimated_cost")
        or itinerary.get("cost_breakdown", {}).get("total_estimated")
    )
    if has_cost:
        passed_checks += 1
    else:
        missing_fields.append("cost_info")

    # 5. Check for date information
    total_checks += 1
    has_dates = False
    trip_summary = itinerary.get("trip_summary", {})
    if trip_summary.get("start_date") and trip_summary.get("end_date"):
        has_dates = True
    elif hotel and hotel.get("check_in_date") and hotel.get("check_out_date"):
        has_dates = True
    if has_dates:
        passed_checks += 1
    else:
        missing_fields.append("dates")

    is_valid = len(missing_fields) == 0
    score = passed_checks / total_checks if total_checks > 0 else 0

    return {
        "is_valid": is_valid,
        "errors": errors,
        "missing_fields": missing_fields,
        "score": score
    }


def format_plan_summary(plan: dict) -> str:
    """
    Create human-readable plan summary.
    """
    if not plan or "itinerary" not in plan:
        return "Invalid plan structure"
    
    itinerary = plan["itinerary"]
    trip = itinerary.get("trip_summary", {})
    cost = itinerary.get("cost_breakdown", {})
    
    summary = f"""
TRAVEL PLAN SUMMARY
{'='*50}

Trip Details:
  Destination: {trip.get('destination', 'N/A')} from {trip.get('origin', 'N/A')}
  Dates: {trip.get('start_date', 'N/A')} to {trip.get('end_date', 'N/A')} ({trip.get('duration_nights', 0)} nights)

Flights:
  Outbound: {plan['itinerary']['flights']['outbound'].get('airline', 'N/A')} - ${plan['itinerary']['flights']['outbound'].get('price_usd', 0)}
  Return: {plan['itinerary']['flights']['return'].get('airline', 'N/A')} - ${plan['itinerary']['flights']['return'].get('price_usd', 0)}

Hotel:
  {itinerary['accommodation'].get('name', 'N/A')} ({itinerary['accommodation'].get('rating', 'N/A')}⭐)
  ${itinerary['accommodation'].get('price_per_night', 0)}/night x {itinerary['accommodation'].get('num_nights', 0)} nights

Activities: {len(itinerary.get('activities', []))} planned

TOTAL COST: ${cost.get('total_estimated', 0):,.2f}
{'='*50}
"""
    return summary
