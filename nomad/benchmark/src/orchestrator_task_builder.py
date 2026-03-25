"""
Utilities for creating and managing Orchestrator tasks
"""
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class OrchestratorTask:
    """Represents an Orchestrator task following ORCHESTRATOR_ANALYSIS_SCHEMA"""
    
    task_id: str
    tier: int
    difficulty: str  # easy, medium, hard
    description: str
    category: str = "orchestrator"
    
    # Input
    input_type: str = "natural_language"  # structured, mixed, natural_language
    input_format: str = "text"  # json, json_plus_nlp, text
    input_content: Dict[str, Any] = None
    input_nlp_query: Optional[str] = None
    
    # Expected Output (matches ORCHESTRATOR_ANALYSIS_SCHEMA)
    expected_intent: str = None  # new_trip, update_constraints, ask_question, confirm_itinerary
    expected_constraints: Dict[str, Any] = None
    expected_delegation: str = None  # logistics, activities, both, none
    expected_response: str = None
    
    # Metadata
    expected_tools: List[str] = None
    tags: List[str] = None
    current_state_constraints: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate the task"""
        assert self.tier in [1, 2, 3], "Tier must be 1, 2, or 3"
        assert self.difficulty in ["easy", "medium", "hard"], "Invalid difficulty"
        assert self.input_type in ["structured", "mixed", "natural_language"], "Invalid input_type"
        assert self.expected_intent in ["new_trip", "update_constraints", "ask_question", "confirm_itinerary"], "Invalid intent"
        assert self.expected_delegation in ["logistics", "activities", "both", "none"], "Invalid delegation"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization"""
        output = {
            "task_id": self.task_id,
            "tier": self.tier,
            "difficulty": self.difficulty,
            "description": self.description,
            "category": self.category,
        }
        
        # Input section
        input_dict = {
            "type": self.input_type,
            "format": self.input_format,
        }
        
        if self.input_type == "structured":
            input_dict["content"] = self.input_content
        elif self.input_type == "mixed":
            input_dict["structured_part"] = self.input_content
            input_dict["nlp_query"] = self.input_nlp_query
        elif self.input_type == "natural_language":
            input_dict["content"] = self.input_content
        
        output["input"] = input_dict
        
        # Expected Output section (matches SCHEMA)
        output["expected_output"] = {
            "intent": self.expected_intent,
            "updated_constraints": self.expected_constraints or {},
            "delegation": self.expected_delegation,
            "response_to_user": self.expected_response
        }
        
        # Optional sections
        if self.current_state_constraints:
            output["current_state_constraints"] = self.current_state_constraints
        
        if self.expected_tools:
            output["expected_tools"] = self.expected_tools
        
        if self.tags:
            output["tags"] = self.tags
        
        return output
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'OrchestratorTask':
        """Create task from dictionary"""
        input_data = data["input"]
        expected_output = data["expected_output"]
        
        task = OrchestratorTask(
            task_id=data["task_id"],
            tier=data["tier"],
            difficulty=data["difficulty"],
            description=data["description"],
            category=data.get("category", "orchestrator"),
            
            input_type=input_data["type"],
            input_format=input_data["format"],
            input_content=input_data.get("content") or input_data.get("structured_part"),
            input_nlp_query=input_data.get("nlp_query"),
            
            expected_intent=expected_output["intent"],
            expected_constraints=expected_output.get("updated_constraints"),
            expected_delegation=expected_output["delegation"],
            expected_response=expected_output["response_to_user"],
            
            expected_tools=data.get("expected_tools"),
            tags=data.get("tags"),
            current_state_constraints=data.get("current_state_constraints"),
        )
        return task


class OrchestratorTaskBuilder:
    """Builder pattern for creating Orchestrator tasks"""
    
    def __init__(self, task_id: str, tier: int, description: str):
        self.task_id = task_id
        self.tier = tier
        self.description = description
        self.difficulty = "easy" if tier == 1 else "medium" if tier == 2 else "hard"
        
        # Input
        self.input_type = None
        self.input_format = None
        self.input_content = {}
        self.input_nlp_query = None
        
        # Expected output
        self.expected_intent = "new_trip"
        self.expected_constraints = {}
        self.expected_delegation = "none"
        self.expected_response = ""
        
        # Metadata
        self.expected_tools = []
        self.tags = []
        self.current_state_constraints = None
    
    def with_structured_input(self, constraints: Dict[str, Any]) -> 'OrchestratorTaskBuilder':
        """Set structured JSON input"""
        self.input_type = "structured"
        self.input_format = "json"
        self.input_content = constraints
        return self
    
    def with_mixed_input(self, structured: Dict[str, Any], nlp_query: str) -> 'OrchestratorTaskBuilder':
        """Set mixed input (JSON + NLP)"""
        self.input_type = "mixed"
        self.input_format = "json_plus_nlp"
        self.input_content = structured
        self.input_nlp_query = nlp_query
        return self
    
    def with_nlp_input(self, query: str) -> 'OrchestratorTaskBuilder':
        """Set natural language input"""
        self.input_type = "natural_language"
        self.input_format = "text"
        self.input_content = query
        return self
    
    def with_intent(self, intent: str) -> 'OrchestratorTaskBuilder':
        """Set expected intent"""
        self.expected_intent = intent
        return self
    
    def with_constraints(self, constraints: Dict[str, Any]) -> 'OrchestratorTaskBuilder':
        """Set expected constraints"""
        self.expected_constraints = constraints
        return self
    
    def with_delegation(self, delegation: str) -> 'OrchestratorTaskBuilder':
        """Set expected delegation"""
        self.expected_delegation = delegation
        return self
    
    def with_response(self, response: str) -> 'OrchestratorTaskBuilder':
        """Set expected response"""
        self.expected_response = response
        return self
    
    def with_tools(self, tools: List[str]) -> 'OrchestratorTaskBuilder':
        """Set expected tools"""
        self.expected_tools = tools
        return self
    
    def with_tags(self, tags: List[str]) -> 'OrchestratorTaskBuilder':
        """Set tags"""
        self.tags = tags
        return self
    
    def with_current_state(self, state: Dict[str, Any]) -> 'OrchestratorTaskBuilder':
        """Set current state constraints (for update scenarios)"""
        self.current_state_constraints = state
        return self
    
    def build(self) -> OrchestratorTask:
        """Build the task"""
        task = OrchestratorTask(
            task_id=self.task_id,
            tier=self.tier,
            difficulty=self.difficulty,
            description=self.description,
            
            input_type=self.input_type,
            input_format=self.input_format,
            input_content=self.input_content,
            input_nlp_query=self.input_nlp_query,
            
            expected_intent=self.expected_intent,
            expected_constraints=self.expected_constraints,
            expected_delegation=self.expected_delegation,
            expected_response=self.expected_response,
            
            expected_tools=self.expected_tools,
            tags=self.tags,
            current_state_constraints=self.current_state_constraints,
        )
        return task


# ============================================================================
# Benchmark → Orchestrator Converter
# ============================================================================

# Map benchmark tool names to orchestrator tool names
TOOL_NAME_MAP = {
    "google_flights": "search_flights",
    "google_hotels": "search_hotels",
    "google_maps": "search_activities",
}


def _parse_constraint_string(constraint: str) -> tuple:
    """
    Parse a single constraint string like 'departure_id: BOS' or 'budget <= 1800'.
    Returns (key, value) tuple.
    """
    # Handle comparison operators: budget < 400, budget <= 1800, price < 200
    for op in ["<=", "<", ">=", ">"]:
        if op in constraint:
            parts = constraint.split(op, 1)
            key = parts[0].strip()
            val = parts[1].strip()
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
            return key, val

    # Handle key: value format
    if ":" in constraint:
        key, val = constraint.split(":", 1)
        key = key.strip()
        val = val.strip()
        try:
            val = int(val)
        except ValueError:
            pass
        return key, val

    return constraint.strip(), True


def _constraints_to_structured(hard_constraints: List[str]) -> Dict[str, Any]:
    """
    Convert a list of benchmark constraint strings into a structured dict
    matching ORCHESTRATOR_ANALYSIS_SCHEMA.updated_constraints.
    """
    result = {}
    interests = []
    dietary_needs = []
    activities = []

    for c_str in hard_constraints:
        key, val = _parse_constraint_string(c_str)

        if key == "departure_id":
            result["origin"] = val
        elif key == "arrival_id":
            result["destination"] = val
        elif key == "outbound_date":
            result["start_date"] = val
        elif key == "return_date":
            result["end_date"] = val
        elif key in ("budget", "budget_usd"):
            result["budget_usd"] = val
        elif key in ("hotel_price", "price"):
            result.setdefault("hotel_budget_per_night", val)
        elif key == "duration":
            # "3 days" → 3
            if isinstance(val, str):
                num = "".join(ch for ch in val if ch.isdigit())
                if num:
                    result["duration_days"] = int(num)
            else:
                result["duration_days"] = val
        elif key == "group_size":
            result["num_travelers"] = val
        elif key == "dietary":
            dietary_needs.append(val)
        elif key == "activity":
            activities.append(val)
        elif key == "amenity":
            interests.append(val)
        elif key == "location":
            # Hotel proximity / destination detail
            if "destination" not in result:
                result["destination"] = val
            else:
                interests.append(f"near {val}")
        elif key == "entity":
            activities.append(val)
        elif key == "hotel":
            interests.append(f"hotel:{val}")
        else:
            # Catch-all: store as-is
            interests.append(f"{key}:{val}" if val is not True else key)

    if dietary_needs:
        result["dietary_needs"] = dietary_needs
    if interests or activities:
        result["interests"] = interests + activities

    return result


def _infer_delegation(tools: List[str]) -> str:
    """Infer delegation type from expected tools."""
    mapped = [TOOL_NAME_MAP.get(t, t) for t in tools]
    has_logistics = any(t in ("search_flights", "search_hotels") for t in mapped)
    has_activities = any(t in ("search_activities",) for t in mapped)
    if has_logistics and has_activities:
        return "both"
    if has_activities:
        return "activities"
    if has_logistics:
        return "logistics"
    return "none"


def _infer_tags(constraints: Dict[str, Any], tools: List[str]) -> List[str]:
    """Infer tags from constraints and tools."""
    tags = []
    mapped = [TOOL_NAME_MAP.get(t, t) for t in tools]
    if "search_flights" in mapped:
        tags.append("flights")
    if "search_hotels" in mapped:
        tags.append("hotels")
    if "search_activities" in mapped:
        tags.append("activities")
    if constraints.get("budget_usd"):
        tags.append("budget")
    if constraints.get("dietary_needs"):
        tags.append("dietary")
    if constraints.get("num_travelers") and constraints["num_travelers"] > 1:
        tags.append("group")
    return tags


def convert_benchmark_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert a single benchmark task dict to one or more orchestrator task dicts.
    T1/T2 tasks produce 1 orchestrator task.
    T3 multi-turn tasks produce N orchestrator tasks (one per turn).
    """
    tier = task["tier"]
    difficulty = {1: "easy", 2: "medium", 3: "hard"}.get(tier, "medium")
    raw_tools = task.get("expected_tools", [])
    mapped_tools = [TOOL_NAME_MAP.get(t, t) for t in raw_tools]
    hard = task.get("constraints", {}).get("hard", [])

    # --- T1 / T2: Single turn ---
    if tier in (1, 2):
        query = task.get("query", "")
        constraints = _constraints_to_structured(hard)
        delegation = _infer_delegation(raw_tools)
        tags = _infer_tags(constraints, raw_tools)

        orch_task = {
            "task_id": f"ORCH-{task['task_id']}",
            "tier": tier,
            "difficulty": difficulty,
            "description": task["description"],
            "category": "orchestrator",
            "input": {
                "type": "natural_language",
                "format": "text",
                "content": query,
            },
            "expected_output": {
                "intent": "new_trip",
                "updated_constraints": constraints,
                "delegation": delegation,
                "response_to_user": "",
            },
            "expected_tools": mapped_tools,
            "tags": tags,
        }

        # Add preferences if present
        if task.get("preferences"):
            orch_task["tags"] = list(set(tags + list(task["preferences"].values())))

        return [orch_task]

    # --- T3: Multi-turn ---
    turns = task.get("turns", [])
    history = task.get("constraints", {}).get("constraint_history", [])
    results = []

    for i, turn_text in enumerate(turns):
        turn_num = i + 1
        is_first = (i == 0)

        # Find the constraint state after this turn
        turn_hard = hard  # default to final state
        for h in history:
            if h.get("after_turn") == turn_num:
                turn_hard = h.get("state", hard)
                break

        constraints = _constraints_to_structured(turn_hard)
        delegation = _infer_delegation(raw_tools)
        tags = _infer_tags(constraints, raw_tools)

        orch_task = {
            "task_id": f"ORCH-{task['task_id']}-turn{turn_num}",
            "tier": tier,
            "difficulty": difficulty,
            "description": f"{task['description']} (turn {turn_num})",
            "category": "orchestrator",
            "input": {
                "type": "natural_language",
                "format": "text",
                "content": turn_text,
            },
            "expected_output": {
                "intent": "new_trip" if is_first else "update_constraints",
                "updated_constraints": constraints,
                "delegation": delegation,
                "response_to_user": "",
            },
            "expected_tools": mapped_tools,
            "tags": tags,
        }

        # For turn 2+, include previous state so orchestrator can diff
        if not is_first and len(history) >= 1:
            prev_state = None
            for h in history:
                if h.get("after_turn") == turn_num - 1:
                    prev_state = _constraints_to_structured(h.get("state", []))
                    break
            if prev_state:
                orch_task["current_state_constraints"] = prev_state

        results.append(orch_task)

    return results


def convert_benchmark_tasks(
    benchmark_path: str,
    output_path: str,
) -> List[Dict[str, Any]]:
    """
    Read benchmark tasks.json, convert all tasks to orchestrator format,
    and save to output_path.
    
    Returns the list of converted orchestrator tasks.
    """
    import os

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_tasks = json.load(f)

    all_orch_tasks = []
    for task in benchmark_tasks:
        converted = convert_benchmark_task(task)
        all_orch_tasks.extend(converted)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_orch_tasks, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(benchmark_tasks)} benchmark tasks → {len(all_orch_tasks)} orchestrator tasks")
    print(f"Saved to: {output_path}")

    return all_orch_tasks


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import os

    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    benchmark_path = os.path.join(script_dir, "..",  "data", "tasks.json")
    output_path = os.path.join(script_dir, "..", "data", "orchestrator_tasks.json")

    # Normalize
    benchmark_path = os.path.normpath(benchmark_path)
    output_path = os.path.normpath(output_path)

    print(f"Source: {benchmark_path}")
    print(f"Output: {output_path}")
    print()

    tasks = convert_benchmark_tasks(benchmark_path, output_path)
