import json
import re
from datetime import datetime
from typing import Dict, List, Tuple
from plan_schema import PLAN_SCHEMA, validate_plan


class NomadEvaluator:
    """
    Evaluates agent performance based on:
    - Constraint Satisfaction Rate (CSR)
    - Tool-Use Accuracy
    - Plan Schema Compliance
    - Itinerary Consistency (temporal/spatial)
    
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

    def evaluate(self, agent_output, task_id=None, hard_constraints=None, expected_tools=None, tool_logs=None):
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

        Returns:
            {
                "task_id": str,
                "overall_score": 0-1,
                "csr_score": 0-1,
                "tool_accuracy": 0-1,
                "schema_compliance": 0-1,
                "itinerary_validity": bool,
                "constraint_breakdown": {constraint: bool},
                "schema_validation": {is_valid, errors, missing_fields},
                "conflict_report": {has_conflicts, errors, warnings}
            }
        """
        # Handle defaults
        if tool_logs is None:
            tool_logs = []
        if expected_tools is None:
            expected_tools = ["flight_search", "hotel_search", "activities_search"]
        if task_id is None:
            task_id = agent_output.get("task_id", "unknown_task")
        
        # Try to get constraints from benchmark task file if available
        if not hard_constraints and task_id in self.tasks:
            task = self.tasks[task_id]
            hard_constraints = task.get("constraints", {}).get("hard", [])
            if not expected_tools or expected_tools == ["flight_search", "hotel_search", "activities_search"]:
                expected_tools = task.get("expected_tools", expected_tools)
        
        # If still no constraints, auto-extract from agent_output
        if not hard_constraints:
            hard_constraints = self._extract_constraints_from_plan(agent_output)

        # 1. Schema Compliance - does output match PLAN_SCHEMA?
        schema_validation = self._validate_schema(agent_output)

        # 2. Constraint Satisfaction Rate (CSR) - does output meet hard constraints?
        csr_results = self._check_constraints(hard_constraints, agent_output)

        # 3. Tool-Use Accuracy - correct tools used?
        tool_accuracy = self._check_tool_accuracy(expected_tools, tool_logs)

        # 4. Itinerary Consistency - no temporal/spatial conflicts?
        conflict_report = self._check_itinerary_consistency(agent_output)

        # Calculate overall score (weighted average)
        overall_score = (
            schema_validation["score"] * 0.25 +
            csr_results["score"] * 0.35 +
            tool_accuracy * 0.20 +
            (1.0 if not conflict_report["has_conflicts"] else 0.5) * 0.20
        )

        return {
            "task_id": task_id,
            "overall_score": round(overall_score, 3),
            "csr_score": round(csr_results["score"], 3),
            "tool_accuracy": round(tool_accuracy, 3),
            "schema_compliance": round(schema_validation["score"], 3),
            "itinerary_validity": schema_validation["is_valid"],
            "constraint_breakdown": csr_results["breakdown"],
            "schema_validation": {
                "is_valid": schema_validation["is_valid"],
                "errors": schema_validation["errors"],
                "missing_fields": schema_validation["missing_fields"]
            },
            "conflict_report": conflict_report,
        }

    def _extract_constraints_from_plan(self, agent_output) -> List[str]:
        """
        Auto-extract constraints from the verified plan.
        
        Used when hard_constraints are not provided.
        
        Returns:
            List of inferred constraints from the plan
        """
        constraints = []
        
        try:
            itinerary = agent_output.get("itinerary", {})
            trip = itinerary.get("trip_summary", {})
            cost = itinerary.get("cost_breakdown", {})
            
            # Extract from trip summary
            origin = trip.get("origin")
            destination = trip.get("destination")
            duration = trip.get("duration_nights")
            total_cost = cost.get("total_estimated", 0)
            
            if origin:
                constraints.append(f"Origin: {origin}")
            if destination:
                constraints.append(f"Destination: {destination}")
            if duration:
                constraints.append(f"Duration: {duration} nights")
            if total_cost:
                constraints.append(f"Budget: ${total_cost}")
        except:
            pass
        
        return constraints if constraints else []

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
        Validates output against hard constraints using schema fields and values.

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

        itinerary = output.get("itinerary", {})
        trip = itinerary.get("trip_summary", {})
        flights = itinerary.get("flights", {})
        hotel = itinerary.get("accommodation", {})
        cost_breakdown = itinerary.get("cost_breakdown", {})

        for constraint in hard_constraints:
            constraint_lower = constraint.lower()
            is_met = False

            # Budget constraint: total_cost <= limit
            if "budget" in constraint_lower or "$" in constraint_lower:
                try:
                    limit = int(re.findall(r"\d+", constraint)[0])
                    total_cost = cost_breakdown.get("total_estimated", 0)
                    is_met = total_cost <= limit
                except (IndexError, ValueError):
                    is_met = False

            # Destination constraint
            elif "destination" in constraint_lower:
                required_dest = constraint.split(":")[-1].strip().lower()
                is_met = required_dest in trip.get("destination", "").lower()

            # Origin constraint
            elif "origin" in constraint_lower or "from" in constraint_lower:
                required_origin = constraint.split(":")[-1].strip().lower()
                is_met = required_origin in trip.get("origin", "").lower()

            # Duration constraint: nights
            elif "night" in constraint_lower or "duration" in constraint_lower:
                try:
                    required_nights = int(re.findall(r"\d+", constraint)[0])
                    actual_nights = trip.get("duration_nights", 0)
                    is_met = actual_nights >= required_nights
                except (IndexError, ValueError):
                    is_met = False

            # Dietary constraint
            elif "dietary" in constraint_lower or "vegan" in constraint_lower or "vegetarian" in constraint_lower:
                dietary_pref = constraint.split(":")[-1].strip().lower()
                # Check in hotel amenities or activity descriptions
                all_text = json.dumps(itinerary).lower()
                is_met = dietary_pref in all_text

            # Hotel rating constraint
            elif "rating" in constraint_lower or "star" in constraint_lower:
                try:
                    min_rating = float(re.findall(r"\d+\.?\d*", constraint)[0])
                    actual_rating = hotel.get("rating", 0)
                    is_met = actual_rating >= min_rating
                except (IndexError, ValueError):
                    is_met = False

            # Dates constraint
            elif "date" in constraint_lower:
                required_start = trip.get("start_date", "")
                is_met = required_start != ""

            else:
                # General keyword matching
                keyword = constraint.split(":")[0].strip().lower()
                all_text = json.dumps(itinerary).lower()
                is_met = keyword in all_text

            breakdown[constraint] = is_met
            if is_met:
                met_count += 1

        score = met_count / len(hard_constraints) if hard_constraints else 1.0
        return {"score": score, "met": met_count, "breakdown": breakdown}


    def _check_tool_accuracy(self, expected_tools: List[str], logs: List[Dict]) -> float:
        """
        Measures tool selection accuracy.
        Checks: (1) all expected tools were used, (2) no hallucinated tools.

        Returns:
            0-1 score
        """
        if not expected_tools:
            return 1.0

        used_tools = [log.get("tool", "") for log in logs]
        used_tools_set = set(used_tools)
        expected_tools_set = set(expected_tools)

        # Precision: tools used were expected
        if used_tools_set:
            precision = len(used_tools_set & expected_tools_set) / len(used_tools_set)
        else:
            precision = 0

        # Recall: all expected tools were used
        recall = len(used_tools_set & expected_tools_set) / len(expected_tools_set)

        # F1 score
        if precision + recall == 0:
            return 0.0
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1


    def _check_itinerary_consistency(self, output) -> Dict:
        """
        Checks for temporal/spatial conflicts in itinerary:
        - Activity times don't overlap
        - Transportation time is feasible
        - Hotel check-out before next hotel check-in
        - Flight times are reasonable

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
            itinerary = output.get("itinerary", {})
            if not itinerary:
                return {"has_conflicts": True, "errors": ["No itinerary found"], "warnings": []}

            # Check flight timing
            flights = itinerary.get("flights", {})
            outbound = flights.get("outbound", {})
            return_flight = flights.get("return", {})

            if outbound and return_flight:
                try:
                    out_departure = outbound.get("departure", "")
                    ret_departure = return_flight.get("departure", "")
                    if out_departure and ret_departure and out_departure >= ret_departure:
                        errors.append("Return flight departs before outbound flight")
                except:
                    pass

            # Check hotel consistency
            hotel = itinerary.get("accommodation", {})
            if hotel:
                check_in = hotel.get("check_in_date", "")
                check_out = hotel.get("check_out_date", "")
                if check_in and check_out:
                    try:
                        if check_in >= check_out:
                            errors.append("Hotel check-out before check-in")
                        num_nights = hotel.get("num_nights", 0)
                        if num_nights <= 0:
                            errors.append("Invalid hotel duration")
                    except:
                        pass

            # Check activity dates are within trip
            activities = itinerary.get("activities", [])
            trip = itinerary.get("trip_summary", {})
            trip_start = trip.get("start_date", "")
            trip_end = trip.get("end_date", "")

            for i, activity in enumerate(activities):
                activity_date = activity.get("date", "")
                try:
                    if trip_start and trip_end and activity_date:
                        if activity_date < trip_start or activity_date > trip_end:
                            errors.append(f"Activity {i+1} date {activity_date} outside trip dates")
                except:
                    pass

                # Check activity duration is reasonable
                duration = activity.get("duration_hours", 0)
                if duration <= 0 or duration > 24:
                    warnings.append(f"Activity {i+1} has unusual duration: {duration} hours")

            # Check cost calculation
            cost_breakdown = itinerary.get("cost_breakdown", {})
            if cost_breakdown:
                total = cost_breakdown.get("total_estimated", 0)
                flights_cost = (
                    outbound.get("price_usd", 0) +
                    return_flight.get("price_usd", 0)
                )
                hotel_cost = hotel.get("total_nights_cost", 0)
                activities_cost = sum(a.get("total_price", 0) for a in activities)

                calculated_total = flights_cost + hotel_cost + activities_cost
                # Allow 10% tolerance for miscellaneous/rounding
                if calculated_total > 0 and total > 0:
                    if abs(total - calculated_total) > calculated_total * 0.1:
                        warnings.append(
                            f"Cost calculation mismatch: reported {total} vs calculated {calculated_total}"
                        )

        except Exception as e:
            errors.append(f"Error during consistency check: {str(e)}")

        return {
            "has_conflicts": len(errors) > 0,
            "errors": errors,
            "warnings": warnings
        }
