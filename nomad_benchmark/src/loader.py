import json
import os


class TaskLoader:
    """
    Handles loading and parsing of the 20-task benchmark.
    Supports single-turn and multi-turn (Tier 3) task structures.
    """

    def __init__(self, file_path="data/tasks.json"):
        self.file_path = file_path
        self.tasks = self._load_file()

    def _load_file(self):
        """Loads the JSON task file from the data directory."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Benchmark file not found at {self.file_path}")
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_task(self, task_id):
        """Retrieves a specific task by its ID."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                return task
        return None

    def get_all_tasks(self, tier=None):
        """
        Returns a list of tasks, optionally filtered by difficulty Tier.
        Tier 1: Static, Tier 2: Full Itinerary, Tier 3: Dynamic.
        """
        if tier:
            return [t for t in self.tasks if t["tier"] == tier]
        return self.tasks

    def format_for_agent(self, task):
        """
        Standardizes the task input for the Agent's orchestrator.
        Orchestrator receives the full conversation history.
            - Tier 1 & 2: Single-turn tasks with empty history.
            - Tier 3: Multi-turn tasks with provided history and current query.
        TODO: In a future iteration, we could add more metadata here (e.g., expected tools)
        to assist the Agent's reasoning layer.
        """
        # Define the core fields we always expect
        base_data = {
            "task_id": task["task_id"],
            "tier": task["tier"],
            "query": task.get("query")
            if task["tier"] < 3
            else task.get("turns", [])[-1],
            "history": task.get("turns", [])[:-1] if task["tier"] == 3 else [],
        }

        # Automatically collect all other fields as 'constraints' or 'metadata'
        # This makes the loader flexible for future fields like 'preferences'
        metadata = {
            "constraints": task.get("constraints", {}),
            "preferences": task.get("preferences", {}),  # Future-proof
            "context": {
                k: v
                for k, v in task.items()
                if k
                not in [
                    "task_id",
                    "tier",
                    "query",
                    "turns",
                    "constraints",
                    "preferences",
                ]
            },
        }

        return {**base_data, **metadata}
