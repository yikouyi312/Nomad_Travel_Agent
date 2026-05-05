import json
import re
from datetime import datetime
from typing import Dict, List, Tuple
from .plan_schema import PLAN_SCHEMA, validate_plan


class NomadEvaluator:
    """
    Evaluates agent performance based on:
    - Constraint Satisfaction Rate (CSR)
    - Tool-Use Accuracy
    - Plan Schema Compliance
    - Itinerary Consistency (temporal/spatial)
    
    Handles both verification output format and PLAN_SCHEMA format.
    Does NOT require a task_file - evaluates plans directly.
    """

    def __init__(self, task_file=None):
        """
        Initialize evaluator.
        
        Args:
            task_file (str, optional): Path to tasks.json for benchmark evaluation.
                If provided, allows evaluation with hard constraints from benchmark.
                If None, evaluator works with explicit constraints passed at eval time.
        """
        self.tasks = {}
        if task_file:
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    self.tasks = {t["task_id"]: t for t in json.load(f)}
            except FileNotFoundError:
                print(f"Warning: {task_file} not found. Running in standalone mode.")

    def evaluate(self, agent_output, task_id=None, hard_constraints=None, expected_tools=None, tool_logs=None, interests=None):
        """
        Main evaluation function with schema-based validation.
        
        Does NOT require task_file or task_id. Can evaluate standalone.

        Args:
            agent_output (dict): The final itinerary plan from the Agent.
            task_id (str, optional): ID for reference. If provided and tasks loaded, uses benchmark constraints.
            hard_constraints (list, optional): List of hard constraints (e.g., ["Budget: $3000", "Destination: Paris"]).
                If not provided, auto-extracts from agent_output.
            expected_tools (list, optional): Expected tools called. Defaults to ["flight_search", "hotel_search", "activities_search"].
            tool_logs (list, optional): Record of tool calls. Defaults to empty list.
            interests (list, optional): List of interest keywords (e.g., ["Broadway show", "musical"]).
                If provided and non-empty, base scores are weighted 90% and interest satisfaction 10%.

        Returns:
            {
                "task_id": str,
                "overall_score": 0-1,
                "csr_score": 0-1,
                "interest_score": 0-1 or None,
                "tool_accuracy": 0-1,
                "schema_compliance": 0-1,
                "itinerary_validity": bool,
                "constraint_breakdown": {constraint: bool},
                "interest_breakdown": {interest: bool} or None,
                "schema_validation": {is_valid, errors, missing_fields},
                "conflict_report": {has_conflicts, errors, warnings}
            }
        """
        # Handle defaults
        if tool_logs is None:
            tool_logs = []
        if expected_tools is None:
            expected_tools = ["search_flights", "search_hotels", "search_places"]
        if task_id is None:
            task_id = agent_output.get("task_id", "unknown_task")
        
        # Try to get constraints from benchmark task file if available
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if not hard_constraints:
                hard_constraints = task.get("constraints", {}).get("hard", [])
            if interests is None:
                # interests may be under expected_output.updated_constraints or constraints
                interests = list(
                    task.get("expected_output", {}).get("updated_constraints", {}).get("interests")
                    or task.get("constraints", {}).get("interests")
                    or []
                )
            if not expected_tools or expected_tools == ["search_flights", "search_hotels", "search_places"]:
                expected_tools = task.get("expected_tools", expected_tools)

            # Hotel star rating: route to hard constraint or interest based on priority
            uc = task.get("expected_output", {}).get("updated_constraints", {})
            _hr = uc.get("preferred_hotel_rating")
            _hp = uc.get("hotel_rating_priority", "soft")
            if _hr is not None:
                if _hp == "hard":
                    if hard_constraints is None:
                        hard_constraints = []
                    hard_constraints.append(f"Hotel rating: at least {_hr} stars")
                else:
                    if interests is None:
                        interests = []
                    interests.append(f"{_hr}-star hotel")

            # Hotel location: always a hard constraint when specified
            _hl = uc.get("hotel_location")
            if _hl:
                if hard_constraints is None:
                    hard_constraints = []
                hard_constraints.append(f"hotel_location: {_hl}")
        
        # If still no constraints, auto-extract from agent_output
        if not hard_constraints:
            hard_constraints = self._extract_constraints_from_plan(agent_output)

        # 1. Schema Compliance - does output match PLAN_SCHEMA?
        schema_validation = self._validate_schema(agent_output)

        # 2. Constraint Satisfaction Rate (CSR) - does output meet hard constraints?
        csr_results = self._check_constraints(hard_constraints, agent_output)

        # 3. Tool-Use Accuracy - correct tools used?
        tool_accuracy = self._check_tool_accuracy(expected_tools, tool_logs, agent_output)

        # 4. Itinerary Consistency - no temporal/spatial conflicts?
        conflict_report = self._check_itinerary_consistency(agent_output)

        # 5. Interest Satisfaction - do activities match user interests?
        interest_results = None
        if interests:
            interest_results = self._check_interests(interests, agent_output)

        # Calculate overall score (weighted average)
        base_score = (
            schema_validation["score"] * 0.25 +
            csr_results["score"] * 0.35 +
            tool_accuracy * 0.20 +
            (1.0 if not conflict_report["has_conflicts"] else 0.5) * 0.20
        )

        if interest_results:
            # 90% base scores + 10% interest satisfaction
            overall_score = base_score * 0.9 + interest_results["score"] * 0.1
        else:
            overall_score = base_score

        return {
            "task_id": task_id,
            "overall_score": round(overall_score, 3),
            "csr_score": round(csr_results["score"], 3),
            "interest_score": round(interest_results["score"], 3) if interest_results else None,
            "tool_accuracy": round(tool_accuracy, 3),
            "schema_compliance": round(schema_validation["score"], 3),
            "itinerary_validity": schema_validation["is_valid"],
            "constraint_breakdown": csr_results["breakdown"],
            "interest_breakdown": interest_results["breakdown"] if interest_results else None,
            "schema_validation": {
                "is_valid": schema_validation["is_valid"],
                "errors": schema_validation["errors"],
                "missing_fields": schema_validation["missing_fields"]
            },
            "conflict_report": conflict_report,
        }

    # ── Data extraction helpers (handle both verification & schema format) ──

    def _get_itinerary(self, agent_output) -> dict:
        """Extract itinerary dict from any format."""
        if "itinerary" in agent_output:
            return agent_output["itinerary"]
        # The output IS the itinerary (flights/hotels at top level)
        if "flights" in agent_output or "hotels" in agent_output:
            return agent_output
        return {}

    def _get_flight_info(self, itinerary) -> dict:
        """Extract normalized flight info from any format."""
        flights = itinerary.get("flights", {})
        outbound = flights.get("outbound", {})

        # Verification format: outbound.flights[] array
        segments = outbound.get("flights", [])
        if segments:
            first = segments[0]
            last = segments[-1]
            return {
                "origin": first.get("departure_airport", {}).get("id", ""),
                "destination": last.get("arrival_airport", {}).get("id", ""),
                "departure_time": first.get("departure_airport", {}).get("time", ""),
                "arrival_time": last.get("arrival_airport", {}).get("time", ""),
                "airline": first.get("airline", ""),
                "flight_number": first.get("flight_number", ""),
                "price": outbound.get("price", 0),
            }

        # Schema format: flat fields
        return {
            "origin": outbound.get("departure", ""),
            "destination": outbound.get("arrival_city", ""),
            "departure_time": outbound.get("departure_time", ""),
            "arrival_time": outbound.get("arrival_time", ""),
            "airline": outbound.get("airline", ""),
            "flight_number": outbound.get("flight_number", ""),
            "price": outbound.get("price_usd", 0),
        }

    def _get_hotel_info(self, itinerary) -> dict:
        """Extract normalized hotel info from any format."""
        hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
        if not hotel:
            return {}

        rate = hotel.get("rate_per_night", {})
        total = hotel.get("total_rate", {})

        # Star class: prefer extracted_hotel_class, fall back to hotel_class
        star_class = 0
        hc = hotel.get("extracted_hotel_class") or hotel.get("hotel_class", 0)
        if isinstance(hc, (int, float)):
            star_class = hc

        return {
            "name": hotel.get("name", ""),
            "address": hotel.get("address", hotel.get("location", "")),
            "description": hotel.get("description", ""),
            "check_in_date": hotel.get("check_in_date", ""),
            "check_out_date": hotel.get("check_out_date", ""),
            "nights": hotel.get("nights", hotel.get("num_nights", 0)),
            "price_per_night": (
                rate.get("extracted_lowest", 0) if isinstance(rate, dict)
                else hotel.get("price_per_night", 0)
            ),
            "total_cost": (
                total.get("extracted_lowest", 0) if isinstance(total, dict)
                else hotel.get("total_nights_cost", 0)
            ),
            "rating": hotel.get("overall_rating", hotel.get("rating", 0)),
            "star_class": star_class,
        }

    def _get_total_cost(self, itinerary) -> float:
        """Get total estimated cost from any format."""
        if "estimated_cost" in itinerary:
            return itinerary["estimated_cost"]
        return itinerary.get("cost_breakdown", {}).get("total_estimated", 0)

    def _get_activities(self, itinerary) -> list:
        """Get activities with normalized field names."""
        activities = itinerary.get("activities", [])
        normalized = []
        for a in activities:
            normalized.append({
                "date": a.get("date", ""),
                "name": a.get("activity", a.get("name", "")),
                "description": a.get("description", ""),
                "cost": a.get("estimated_cost", a.get("price_per_person", a.get("total_price", 0))),
                "time": a.get("time", ""),
                "duration_hours": a.get("duration_hours", 0),
            })
        return normalized

    # ── Constraint extraction ──

    def _extract_constraints_from_plan(self, agent_output) -> List[str]:
        """
        Auto-extract constraints from the plan.
        Checks explicit constraints field first, then infers from flight/hotel data.
        """
        constraints = []

        # 1. Check for explicit constraints field (verification format)
        explicit = agent_output.get("constraints", {})
        if explicit:
            if explicit.get("origin"):
                constraints.append(f"Origin: {explicit['origin']}")
            if explicit.get("destination"):
                constraints.append(f"Destination: {explicit['destination']}")
            if explicit.get("start_date"):
                constraints.append(f"Start_date: {explicit['start_date']}")
            if explicit.get("end_date"):
                constraints.append(f"End_date: {explicit['end_date']}")
            if explicit.get("budget_usd"):
                constraints.append(f"Budget: ${explicit['budget_usd']}")
            if constraints:
                return constraints

        # 2. Infer from itinerary data
        itinerary = self._get_itinerary(agent_output)
        flight_info = self._get_flight_info(itinerary)
        hotel_info = self._get_hotel_info(itinerary)

        if flight_info.get("origin"):
            constraints.append(f"Origin: {flight_info['origin']}")
        if flight_info.get("destination"):
            constraints.append(f"Destination: {flight_info['destination']}")
        if hotel_info.get("check_in_date"):
            constraints.append(f"Start_date: {hotel_info['check_in_date']}")
        if hotel_info.get("check_out_date"):
            constraints.append(f"End_date: {hotel_info['check_out_date']}")

        # 3. Fallback: try trip_summary (schema format)
        if not constraints:
            trip = itinerary.get("trip_summary", {})
            if trip.get("origin"):
                constraints.append(f"Origin: {trip['origin']}")
            if trip.get("destination"):
                constraints.append(f"Destination: {trip['destination']}")
            if trip.get("start_date"):
                constraints.append(f"Start_date: {trip['start_date']}")
            if trip.get("end_date"):
                constraints.append(f"End_date: {trip['end_date']}")

        return constraints

    def _validate_schema(self, agent_output) -> Dict:
        """
        Validates output against PLAN_SCHEMA.

        Returns:
            {
                "is_valid": bool,
                "score": 0-1,
                "errors": [error messages],
                "missing_fields": [field names]
            }
        """
        try:
            return validate_plan(agent_output)
        except Exception as e:
            return {
                "is_valid": False,
                "score": 0,
                "errors": [str(e)],
                "missing_fields": []
            }

    def _check_constraints(self, hard_constraints, output):
        """
        Validates output against hard constraints.
        Uses normalized data helpers to handle both verification and schema formats.

        Returns:
            {
                "score": 0-1,
                "met": int,
                "breakdown": {constraint: bool}
            }
        """
        met_count = 0
        breakdown = {}

        if not hard_constraints:
            return {"score": 1.0, "met": 0, "breakdown": {}}

        itinerary = self._get_itinerary(output)
        flight_info = self._get_flight_info(itinerary)
        hotel_info = self._get_hotel_info(itinerary)
        total_cost = self._get_total_cost(itinerary)
        all_text = json.dumps(output).lower()

        for constraint in hard_constraints:
            constraint_lower = constraint.lower()
            is_met = False

            # Budget constraint: total_cost <= limit
            if "budget" in constraint_lower or "$" in constraint_lower:
                try:
                    limit = int(re.findall(r"\d+", constraint)[0])
                    is_met = 0 < total_cost <= limit
                except (IndexError, ValueError):
                    is_met = False

            # Destination constraint
            elif "destination" in constraint_lower:
                required_dest = constraint.split(":")[-1].strip().lower()
                actual_dest = flight_info.get("destination", "").lower()
                is_met = required_dest in actual_dest or actual_dest in required_dest

            # Origin constraint
            elif "origin" in constraint_lower or "from" in constraint_lower:
                required_origin = constraint.split(":")[-1].strip().lower()
                actual_origin = flight_info.get("origin", "").lower()
                is_met = required_origin in actual_origin or actual_origin in required_origin

            # Duration constraint: nights
            elif "night" in constraint_lower or "duration" in constraint_lower:
                try:
                    required_nights = int(re.findall(r"\d+", constraint)[0])
                    actual_nights = hotel_info.get("nights", 0)
                    is_met = actual_nights >= required_nights
                except (IndexError, ValueError):
                    is_met = False

            # Dietary constraint
            elif "dietary" in constraint_lower or "vegan" in constraint_lower or "vegetarian" in constraint_lower:
                dietary_pref = constraint.split(":")[-1].strip().lower()
                is_met = dietary_pref in all_text

            # Start date constraint (must be before "star" check)
            elif "start_date" in constraint_lower:
                required_date = constraint.split(":")[-1].strip()
                actual_date = hotel_info.get("check_in_date", "")
                is_met = required_date == actual_date

            # End date constraint
            elif "end_date" in constraint_lower:
                required_date = constraint.split(":")[-1].strip()
                actual_date = hotel_info.get("check_out_date", "")
                is_met = required_date == actual_date

            # Hotel rating constraint (after start/end_date to avoid "star" matching "start")
            elif "rating" in constraint_lower or ("star" in constraint_lower and "start" not in constraint_lower):
                try:
                    min_rating = float(re.findall(r"\d+\.?\d*", constraint)[0])
                    # Use star_class (hotel class) first; fall back to review rating
                    actual = hotel_info.get("star_class", 0) or hotel_info.get("rating", 0)
                    is_met = actual >= min_rating
                except (IndexError, ValueError):
                    is_met = False

            # Hotel location constraint: check hotel name/address
            elif "hotel_location" in constraint_lower or "hotel location" in constraint_lower:
                required_loc = constraint.split(":")[-1].strip().lower()
                hotel_name = hotel_info.get("name", "").lower()
                hotel_addr = hotel_info.get("address", "").lower()
                hotel_desc = hotel_info.get("description", "").lower()
                combined = f"{hotel_name} {hotel_addr} {hotel_desc}"
                # Strip common prefixes like "near", "close to"
                loc_keywords = required_loc.replace("near ", "").replace("close to ", "").replace("downtown", "downtown").strip()
                is_met = any(kw in combined for kw in loc_keywords.split() if len(kw) > 2) or loc_keywords in all_text

            # General date constraint
            elif "date" in constraint_lower:
                is_met = hotel_info.get("check_in_date", "") != ""

            else:
                # General keyword matching
                keyword = constraint.split(":")[-1].strip().lower()
                is_met = keyword in all_text

            breakdown[constraint] = is_met
            if is_met:
                met_count += 1

        score = met_count / len(hard_constraints) if hard_constraints else 1.0
        return {"score": score, "met": met_count, "breakdown": breakdown}

    def _check_interests(self, interests: List[str], output) -> Dict:
        """
        Checks how many user interests are reflected in the plan output.
        Uses structural checks for flight/hotel-specific interests and
        falls back to keyword matching for the rest.

        Returns:
            {
                "score": 0-1,
                "met": int,
                "breakdown": {interest: bool}
            }
        """
        if not interests:
            return {"score": 1.0, "met": 0, "breakdown": {}}

        all_text = json.dumps(output).lower()
        itinerary = self._get_itinerary(output)
        hotel_info = self._get_hotel_info(itinerary)
        outbound = itinerary.get("flights", {}).get("outbound", {})
        segments = outbound.get("flights", [])
        layovers = outbound.get("layovers", [])

        # Handle flat format: if no nested "flights" array but outbound has
        # departure_airport, treat the outbound object itself as 1 segment
        if not segments and outbound.get("departure_airport"):
            segments = [outbound]

        met_count = 0
        breakdown = {}

        for interest in interests:
            interest_lower = interest.lower()
            is_met = False

            # ── Hotel star rating (e.g. "3-star hotel", "4-star hotel") ──
            star_match = re.match(r"(\d+)\s*-?\s*star", interest_lower)
            if star_match:
                min_rating = float(star_match.group(1))
                # Use star_class from normalized hotel info; >= so 4-star satisfies 3-star
                actual = hotel_info.get("star_class", 0) or hotel_info.get("rating", 0)
                is_met = actual >= min_rating

            # ── Nonstop / direct flight ──
            elif "nonstop" in interest_lower or "non-stop" in interest_lower or "direct" in interest_lower:
                is_met = len(segments) == 1 and len(layovers) == 0

            # ── Morning departure ──
            elif "morning" in interest_lower and "departure" in interest_lower:
                if segments:
                    dep_time = segments[0].get("departure_airport", {}).get("time", "")
                    try:
                        hour = int(dep_time.split()[-1].split(":")[0]) if dep_time else 99
                        is_met = hour < 12
                    except (ValueError, IndexError):
                        is_met = False

            # ── Afternoon departure ──
            elif "afternoon" in interest_lower and "departure" in interest_lower:
                if segments:
                    dep_time = segments[0].get("departure_airport", {}).get("time", "")
                    try:
                        hour = int(dep_time.split()[-1].split(":")[0]) if dep_time else -1
                        is_met = 12 <= hour < 18
                    except (ValueError, IndexError):
                        is_met = False

            # ── Evening departure ──
            elif "evening" in interest_lower and "departure" in interest_lower:
                if segments:
                    dep_time = segments[0].get("departure_airport", {}).get("time", "")
                    try:
                        hour = int(dep_time.split()[-1].split(":")[0]) if dep_time else -1
                        is_met = hour >= 18
                    except (ValueError, IndexError):
                        is_met = False

            # ── No basic economy ──
            elif "no basic economy" in interest_lower or "no basic" in interest_lower:
                if segments:
                    classes = [seg.get("travel_class", "").lower() for seg in segments]
                    is_met = all("basic" not in c for c in classes)
                else:
                    is_met = False

            # ── Fallback: keyword matching ──
            else:
                is_met = interest_lower in all_text

            breakdown[interest] = is_met
            if is_met:
                met_count += 1

        score = met_count / len(interests)
        return {"score": score, "met": met_count, "breakdown": breakdown}

    def _check_tool_accuracy(self, expected_tools: List[str], logs: List[Dict], agent_output=None) -> float:
        """
        Measures tool selection accuracy.
        Checks: (1) all expected tools were used, (2) no hallucinated tools.
        
        If no logs provided, infers tool usage from plan content.

        Returns:
            0-1 score
        """
        if not expected_tools:
            return 1.0

        used_tools = [log.get("tool", "") for log in logs]
        
        # If no tool logs, infer from plan data
        # Use names matching orchestrator_tasks.json: search_flights, search_hotels, search_places
        if not used_tools and agent_output:
            itinerary = self._get_itinerary(agent_output)
            flights = itinerary.get("flights", {})
            hotel = itinerary.get("hotels", itinerary.get("accommodation", {}))
            activities = itinerary.get("activities", [])
            
            if flights and flights.get("outbound"):
                used_tools.append("search_flights")
            if hotel and (hotel.get("name") if isinstance(hotel, dict) else False):
                used_tools.append("search_hotels")
            if activities:
                used_tools.append("search_places")

        used_tools_set = set(used_tools)
        expected_tools_set = set(expected_tools)

        # Normalize aliases: search_activities ↔ search_places
        _aliases = {"search_activities": "search_places", "search_places": "search_activities"}
        used_normalized = set()
        for t in used_tools_set:
            used_normalized.add(t)
            if t in _aliases:
                used_normalized.add(_aliases[t])
        expected_normalized = set()
        for t in expected_tools_set:
            expected_normalized.add(t)
            if t in _aliases:
                expected_normalized.add(_aliases[t])

        # Precision: tools used were expected
        if used_tools_set:
            precision = len(used_tools_set & expected_normalized) / len(used_tools_set)
        else:
            precision = 0

        # Recall: all expected tools were used
        recall = len(expected_tools_set & used_normalized) / len(expected_tools_set)

        # F1 score
        if precision + recall == 0:
            return 0.0
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1


    def _check_itinerary_consistency(self, output) -> Dict:
        """
        Checks for temporal/spatial conflicts in itinerary.
        Uses normalized helpers to handle both verification and schema formats.

        Returns:
            {
                "has_conflicts": bool,
                "errors": [error descriptions],
                "warnings": [warning descriptions]
            }
        """
        errors = []
        warnings = []

        try:
            itinerary = self._get_itinerary(output)
            if not itinerary:
                return {"has_conflicts": True, "errors": ["No itinerary found"], "warnings": []}

            flight_info = self._get_flight_info(itinerary)
            hotel_info = self._get_hotel_info(itinerary)
            activities = self._get_activities(itinerary)
            total_cost = self._get_total_cost(itinerary)

            # Check flight has origin and destination
            if not flight_info.get("origin"):
                warnings.append("No departure airport found")
            if not flight_info.get("destination"):
                warnings.append("No arrival airport found")

            # Check hotel consistency
            check_in = hotel_info.get("check_in_date", "")
            check_out = hotel_info.get("check_out_date", "")
            if check_in and check_out:
                if check_in >= check_out:
                    errors.append("Hotel check-out before check-in")
                nights = hotel_info.get("nights", 0)
                if nights <= 0:
                    errors.append("Invalid hotel duration")

            # Check activity dates are within trip dates
            trip_start = check_in  # Use hotel check-in as trip start
            trip_end = check_out    # Use hotel check-out as trip end

            for i, activity in enumerate(activities):
                activity_date = activity.get("date", "")
                if trip_start and trip_end and activity_date:
                    if activity_date < trip_start or activity_date > trip_end:
                        errors.append(f"Activity {i+1} date {activity_date} outside trip dates")

            # Check cost calculation
            if total_cost > 0:
                flight_cost = flight_info.get("price", 0)
                hotel_cost = hotel_info.get("total_cost", 0)
                activities_cost = sum(a.get("cost", 0) for a in activities)

                calculated_total = flight_cost + hotel_cost + activities_cost
                if calculated_total > 0:
                    # Allow 15% tolerance for miscellaneous/rounding/return flight
                    if abs(total_cost - calculated_total) > calculated_total * 0.15:
                        warnings.append(
                            f"Cost calculation mismatch: reported ${total_cost} vs calculated ${calculated_total}"
                        )

        except Exception as e:
            errors.append(f"Error during consistency check: {str(e)}")

        return {
            "has_conflicts": len(errors) > 0,
            "errors": errors,
            "warnings": warnings
        }

    def evaluate_from_repo(self, task_id, plan_repo_dir=None, hard_constraints=None, expected_tools=None, tool_logs=None):
        """
        Evaluate a plan loaded from PlanRepository by task_id.
        
        Args:
            task_id (str): Task ID to load plan from repository
            plan_repo_dir (str): Directory where plans are stored
            hard_constraints (list, optional): Override constraints. If not provided, auto-extracts from plan.
            expected_tools (list, optional): Override expected tools
            tool_logs (list, optional): Override tool logs
        
        Returns:
            Evaluation result dict (same as evaluate())
        
        Raises:
            FileNotFoundError: If plan not found in repository
        """
        try:
            from .plan_repository import PlanRepository
        except ImportError:
            raise ImportError("PlanRepository not found. Please ensure plan_repository.py is available.")
        
        repo = PlanRepository(base_dir=plan_repo_dir)
        
        # Load plan from repository
        plan = repo.load_plan(task_id)
        
        print(f"✓ Loaded plan from repository: {task_id}")
        
        # Evaluate the loaded plan
        return self.evaluate(
            agent_output=plan,
            task_id=task_id,
            hard_constraints=hard_constraints,
            expected_tools=expected_tools,
            tool_logs=tool_logs
        )
