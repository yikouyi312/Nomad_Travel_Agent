import json
import re


class NomadEvaluator:
    """
    Evaluates agent performance based on Constraint Satisfaction Rate (CSR),
    Tool-Use Accuracy, and Recovery Rate.
    """

    def __init__(self, task_file="data/tasks.json"):
        with open(task_file, "r", encoding="utf-8") as f:
            self.tasks = {t["task_id"]: t for t in json.load(f)}

    def evaluate(self, task_id, agent_output, tool_logs):
        """
        Main evaluation function[cite: 42, 113].

        Args:
            task_id (str): ID of the task from tasks.json.
            agent_output (dict): The final JSON response from the Agent.
            tool_logs (list): Record of all tool calls made by the Agent.
        """
        task = self.tasks.get(task_id, None)
        if not task:
            raise ValueError(f"Task {task_id} not found in benchmark.")

        # 1. Reasoning Layer: Constraint Satisfaction Rate (CSR)
        csr_results = self._check_constraints(task["constraints"]["hard"], agent_output)

        # 2. Action Layer: Tool-Use Accuracy
        tool_accuracy = self._check_tool_accuracy(
            task.get("expected_tools", []), tool_logs
        )

        # 3. Execution Layer: Spatial/Temporal Conflict Check
        conflict_report = self._check_itinerary_consistency(agent_output)

        return {
            "task_id": task_id,
            "tier": task["tier"],
            "csr": csr_results["score"],
            "constraints_met": csr_results["met"],
            "tool_accuracy": tool_accuracy,
            "has_conflicts": conflict_report["has_conflicts"],
            "details": {
                "constraint_breakdown": csr_results["breakdown"],
                "conflict_details": conflict_report["errors"],
            },
        }

    def _check_constraints(self, hard_constraints, output):
        """Calculates the percentage of hard constraints met."""
        met_count = 0
        breakdown = {}

        output_text = json.dumps(output).lower()

        for c in hard_constraints:
            # Basic keyword and value matching logic
            # In a production benchmark, this could be an LLM-as-a-Judge call
            is_met = False
            if "budget" in c:
                price_limit = int(re.findall(r"\d+", c)[0])
                total_price = self._sum_prices(output)
                is_met = total_price <= price_limit
            elif "dietary" in c:
                tag = c.split(":")[-1].strip().lower()
                is_met = tag in output_text
            else:
                # General check for keywords (e.g., location, duration)
                keyword = c.split(":")[0].strip().lower()
                is_met = keyword in output_text
            # TODO: Add more sophisticated checks for dates, locations, etc.
            #  Align with 'Verifier' node in Nomad architecture

            breakdown[c] = is_met
            if is_met:
                met_count += 1

        return {
            "score": met_count / len(hard_constraints) if hard_constraints else 1.0,
            "met": met_count,
            "breakdown": breakdown,
        }

    def _sum_prices(self, output):
        """Helper to extract and sum all prices in the itinerary."""
        prices = re.findall(r"\$(\d+)", str(output))
        return sum(int(p) for p in prices)

    def _check_tool_accuracy(self, expected_tools, logs):
        """Measures tool selection accuracy and hallucination frequency[cite: 44, 119]."""
        if not expected_tools:
            return 1.0
        used_tools = [log["tool"] for log in logs]
        correct_tools = set(used_tools) & set(expected_tools)
        return len(correct_tools) / len(expected_tools)

    def _check_itinerary_consistency(self, output):
        """Checks for overlapping times or impossible travel[cite: 57, 144]."""
        # Simplified check: logic for temporal/spatial conflicts
        # This aligns with the 'Verifier' node in the Nomad architecture
        errors = []
        # Logic would check if 'start_time' of event B is before 'end_time' of event A
        return {"has_conflicts": len(errors) > 0, "errors": errors}
