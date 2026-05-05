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

    # Detect what this plan actually covers (not all plans have all categories)
    has_flight_data = bool(itinerary.get("flights", {}).get("outbound") or itinerary.get("flights", {}).get("return"))
    has_hotel_data = bool(itinerary.get("hotels", itinerary.get("accommodation", {})))
    has_activity_data = bool(itinerary.get("activities"))

    # 1. Check for flights (only if plan has flight data)
    if has_flight_data:
        total_checks += 1
        passed_checks += 1  # already confirmed above

    # 2. Check for accommodation (only if plan has hotel data)
    if has_hotel_data:
        total_checks += 1
        hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
        if hotel and hotel.get("name"):
            passed_checks += 1
        else:
            missing_fields.append("accommodation")

    # 3. Check for activities (only if plan has activity data)
    if has_activity_data:
        total_checks += 1
        passed_checks += 1  # already confirmed above

    # If no category detected at all, fail everything
    if not (has_flight_data or has_hotel_data or has_activity_data):
        total_checks += 3
        missing_fields.extend(["flights", "accommodation", "activities"])

    # 4. Check for cost info (always required)
    total_checks += 1
    has_cost = (
        itinerary.get("estimated_cost")
        or itinerary.get("estimated_total_cost")
        or itinerary.get("cost_breakdown", {}).get("total_estimated")
    )
    if has_cost:
        passed_checks += 1
    else:
        missing_fields.append("cost_info")

    # 5. Check for date information (only if hotel or trip_summary present)
    total_checks += 1
    has_dates = False
    trip_summary = itinerary.get("trip_summary", {})
    if trip_summary.get("start_date") and trip_summary.get("end_date"):
        has_dates = True
    else:
        hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
        if hotel and isinstance(hotel, dict):
            # PLAN_SCHEMA format: explicit check_in_date / check_out_date
            if hotel.get("check_in_date") and hotel.get("check_out_date"):
                has_dates = True
            # SerpAPI format: total_rate implies dates were specified in search
            elif hotel.get("total_rate") or hotel.get("rate_per_night"):
                has_dates = True
        if not has_dates and has_flight_data and not has_hotel_data:
            # Flight-only plans: dates are implicit in flight times
            flights = itinerary.get("flights", {})
            outbound = flights.get("outbound", {})
            segs = outbound.get("flights", [])
            if segs and segs[0].get("departure_airport", {}).get("time"):
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
    Handles both PLAN_SCHEMA format and raw SerpAPI/verification format.
    Follows the same style as format_complete_itinerary().
    """
    if not plan or not isinstance(plan, dict):
        return "Invalid plan structure"

    # Unwrap metadata envelope if present
    if "plan" in plan and "metadata" in plan:
        plan = plan["plan"]

    # Keep reference to full plan data (for LLM reasoning fields)
    plan_data = plan

    # Get itinerary (may be nested or top-level)
    itinerary = plan.get("itinerary", plan)
    if not isinstance(itinerary, dict):
        return "Invalid plan structure"

    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("✈️  COMPLETE TRAVEL ITINERARY")
    lines.append("=" * 70)

    # Validity status
    is_valid = plan_data.get("is_valid")
    status = plan_data.get("status")
    issues = plan_data.get("issues", [])
    hard_violated = (plan_data.get("constraint_validation", {})
                     .get("hard_constraints_violated", []))

    if is_valid is True or status == "approved":
        lines.append("\n✅ STATUS: APPROVED")
    elif is_valid is False or status in ("requires_revision", "invalid"):
        lines.append("\n❌ STATUS: REQUIRES REVISION")
        for issue in issues:
            lines.append(f"  • {issue}")
        for v in hard_violated:
            lines.append(f"  • {v}")
    # else: status unknown, skip

    # ── Flights ──
    def _format_flat_flight(f: dict) -> list:
        """Format a flat flight dict (departure_airport, airline, etc.) into display lines."""
        fl = []
        dep = f.get("departure_airport", {})
        arr = f.get("arrival_airport", {})
        if isinstance(dep, dict) and isinstance(arr, dict):
            fl.append(f"  • route: {dep.get('id', '?')} → {arr.get('id', '?')}")
            dep_time = dep.get("time", "")
            arr_time = arr.get("time", "")
            if dep_time or arr_time:
                fl.append(f"  • time: {dep_time} → {arr_time}")
        airline = f.get("airline", "")
        fnum = f.get("flight_number", "")
        if airline:
            fl.append(f"  • airline: {airline}{(' ' + fnum) if fnum else ''}")
        tclass = f.get("travel_class", "")
        legroom = f.get("legroom", "")
        if tclass:
            fl.append(f"  • class: {tclass}{(', legroom ' + str(legroom)) if legroom else ''}")
        dur = f.get("duration")
        if dur:
            fl.append(f"  • duration: {dur // 60}h {dur % 60}m")
        price = f.get("price")
        trip_type = f.get("type", "")
        if price:
            tag = f" ({trip_type})" if trip_type else ""
            fl.append(f"  • price: ${price}{tag}")
        exts = f.get("extensions", [])
        if exts and isinstance(exts, list):
            fl.append(f"  • notes: {', '.join(str(e) for e in exts)}")
        return fl

    flights = itinerary.get("flights", {})
    outbound = flights.get("outbound", {})
    ret = flights.get("return", {})

    if outbound or ret:
        lines.append("\n" + "-" * 70)
        lines.append("✈️  FLIGHTS")
        lines.append("-" * 70)

        if outbound and isinstance(outbound, dict):
            lines.append(f"\nOUTBOUND FLIGHT:")
            # Flat format (airline, departure_airport, etc. at top level)
            if "airline" in outbound or "departure_airport" in outbound:
                lines.extend(_format_flat_flight(outbound))
            else:
                # SerpAPI nested format
                segments = outbound.get("flights", [])
                first_dep = segments[0].get("departure_airport", {}) if segments else {}
                last_arr = segments[-1].get("arrival_airport", {}) if segments else {}
                price = outbound.get("price", 0)
                trip_type = outbound.get("type", "")
                stops = len(segments) - 1
                stop_txt = "nonstop" if stops == 0 else f"{stops} stop"
                dur_min = outbound.get("total_duration", 0)
                dur_str = f"{dur_min // 60}h {dur_min % 60}m" if dur_min else ""
                price_tag = f"${price} (round trip)" if trip_type == "Round trip" else f"${price}"

                lines.append(f"  • route: {first_dep.get('id','?')} → {last_arr.get('id','?')}")
                lines.append(f"  • stops: {stop_txt}")
                if dur_str:
                    lines.append(f"  • duration: {dur_str}")
                lines.append(f"  • price: {price_tag}")

                for i, seg in enumerate(segments):
                    dep = seg.get("departure_airport", {})
                    arr = seg.get("arrival_airport", {})
                    airline = seg.get("airline", "?")
                    fnum = seg.get("flight_number", "")
                    aircraft = seg.get("airplane", "")
                    tclass = seg.get("travel_class", "")
                    seg_dur = seg.get("duration", 0)
                    seg_dur_str = f"{seg_dur // 60}h {seg_dur % 60}m" if seg_dur else ""
                    lines.append(f"  • segment_{i+1}: {airline} {fnum}  {dep.get('id','')} {dep.get('time','')} → {arr.get('id','')} {arr.get('time','')}  ({seg_dur_str}, {aircraft}, {tclass})")

                for lo in outbound.get("layovers", []):
                    lines.append(f"  • layover: {lo.get('name','')} ({lo.get('duration',0)} min)")

                carbon = outbound.get("carbon_emissions", {})
                if carbon:
                    kg = carbon.get("this_flight", 0) / 1000
                    diff = carbon.get("difference_percent", 0)
                    sign = "+" if diff > 0 else ""
                    lines.append(f"  • carbon: {kg:.0f} kg CO₂ ({sign}{diff}% vs typical)")

        is_round_trip = outbound.get("type") == "Round trip" if isinstance(outbound, dict) else False
        has_return_detail = ret and isinstance(ret, dict) and (
            ret.get("flights") or ret.get("departure_airport") or ret.get("airline")
        )
        if is_round_trip and not has_return_detail:
            lines.append(f"\nRETURN FLIGHT:")
            lines.append("  • included in round-trip fare (return leg selected at booking)")
        elif ret and isinstance(ret, dict):
            lines.append(f"\nRETURN FLIGHT:")
            # Flat format (airline, departure_airport, etc. at top level)
            if "airline" in ret or "departure_airport" in ret:
                lines.extend(_format_flat_flight(ret))
            else:
                # SerpAPI nested format
                segments = ret.get("flights", [])
                first_dep = segments[0].get("departure_airport", {}) if segments else {}
                last_arr = segments[-1].get("arrival_airport", {}) if segments else {}
                price = ret.get("price", 0)
                stops = len(segments) - 1
                stop_txt = "nonstop" if stops == 0 else f"{stops} stop"
                dur_min = ret.get("total_duration", 0)
                dur_str = f"{dur_min // 60}h {dur_min % 60}m" if dur_min else ""

                lines.append(f"  • route: {first_dep.get('id','?')} → {last_arr.get('id','?')}")
                lines.append(f"  • stops: {stop_txt}")
                if dur_str:
                    lines.append(f"  • duration: {dur_str}")
                if price:
                    lines.append(f"  • price: ${price}")

                for i, seg in enumerate(segments):
                    dep = seg.get("departure_airport", {})
                    arr = seg.get("arrival_airport", {})
                    airline = seg.get("airline", "?")
                    fnum = seg.get("flight_number", "")
                    aircraft = seg.get("airplane", "")
                    tclass = seg.get("travel_class", "")
                    seg_dur = seg.get("duration", 0)
                    seg_dur_str = f"{seg_dur // 60}h {seg_dur % 60}m" if seg_dur else ""
                    lines.append(f"  • segment_{i+1}: {airline} {fnum}  {dep.get('id','')} {dep.get('time','')} → {arr.get('id','')} {arr.get('time','')}  ({seg_dur_str}, {aircraft}, {tclass})")

                for lo in ret.get("layovers", []):
                    lines.append(f"  • layover: {lo.get('name','')} ({lo.get('duration',0)} min)")

    # ── Hotels ──
    hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
    if hotel and isinstance(hotel, dict) and (hotel.get("name") or hotel.get("type") == "hotel"):
        lines.append("\n" + "-" * 70)
        lines.append("🏨 HOTELS")
        lines.append("-" * 70)

        for key, value in hotel.items():
            if key not in ("check_in", "check_out", "check_in_date", "check_out_date",
                           "nights", "num_nights", "rate_per_night", "total_rate",
                           "price_per_night", "total_nights_cost"):
                lines.append(f"  • {key}: {value}")

        # Price info
        rate = hotel.get("rate_per_night", {})
        ppn = rate.get("extracted_lowest", 0) if isinstance(rate, dict) else hotel.get("price_per_night", 0)
        total_r = hotel.get("total_rate", {})
        h_total = total_r.get("extracted_lowest", 0) if isinstance(total_r, dict) else hotel.get("total_nights_cost", 0)
        if ppn:
            lines.append(f"  • price_per_night: ${ppn}")
        if h_total:
            lines.append(f"  • total_cost: ${h_total}")

        # Check-in/out
        check_in = hotel.get("check_in") or hotel.get("check_in_date")
        check_out = hotel.get("check_out") or hotel.get("check_out_date")
        num_nights = hotel.get("nights") or hotel.get("num_nights")

        if check_in:
            lines.append(f"\n  CHECK-IN:  {check_in}")
        if check_out:
            lines.append(f"  CHECK-OUT: {check_out}")
        if num_nights:
            lines.append(f"  DURATION:  {num_nights} nights")

    # ── Activities ──
    activities = itinerary.get("activities", [])
    if activities:
        lines.append("\n" + "-" * 70)
        lines.append("🎯 ACTIVITIES & DINING")
        lines.append("-" * 70)

        for i, act in enumerate(activities, 1):
            day = act.get("day_number", "")
            date = act.get("date", "")
            time_str = act.get("time", "")
            dur = act.get("duration_hours", "")
            name = act.get("name", act.get("title", "Activity"))
            atype = act.get("type", "")
            price = act.get("price_per_person", act.get("total_price", ""))
            location = act.get("location", act.get("address", ""))
            desc = act.get("description", "")

            header = f"  {i}. {name}"
            if atype:
                header += f" [{atype}]"
            lines.append(header)
            if day or date:
                day_info = f"Day {day}" if day else ""
                if date:
                    day_info += f" ({date})" if day_info else date
                if time_str:
                    day_info += f" at {time_str}"
                if dur:
                    day_info += f"  ~{dur}h"
                lines.append(f"     {day_info}")
            if location:
                lines.append(f"     📍 {location}")
            if price:
                lines.append(f"     💲 ${price}/person")
            if desc:
                lines.append(f"     {desc[:120]}")

    # ── Cost Summary ──
    cost = itinerary.get("cost_breakdown", {})
    total_cost = (cost.get("total_estimated", 0)
                  or itinerary.get("estimated_total_cost", 0)
                  or itinerary.get("estimated_cost", 0))

    if total_cost:
        lines.append("\n" + "-" * 70)
        lines.append("💰 COST SUMMARY")
        lines.append("-" * 70)
        lines.append(f"  Total Estimated Cost: ${total_cost:,.2f}")

    # ── Final message ──
    lines.append("\n" + "=" * 70)

    reasoning = plan_data.get("reasoning", "")
    message = plan_data.get("final_message_to_user", "")
    constraints_met = plan_data.get("constraints_met")

    if reasoning:
        lines.append(f"📝 Agent Reasoning: {reasoning}")
    if message:
        lines.append(f"📝 {message}")
    if constraints_met is not None:
        lines.append(f"📝 Constraints Met: {'Yes' if constraints_met else 'No'}")

    lines.append("=" * 70)

    return "\n".join(lines)
