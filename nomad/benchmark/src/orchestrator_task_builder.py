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
    input_type: str  # structured, mixed, natural_language
    input_format: str  # json, json_plus_nlp, text
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


# Example usage
if __name__ == "__main__":
    # Example 1: Using builder pattern
    task1 = (OrchestratorTaskBuilder("ORCH-T7", 1, "Simple flight search")
        .with_structured_input({
            "origin": "LAX",
            "destination": "MIA",
            "start_date": "2026-07-01",
            "end_date": "2026-07-10"
        })
        .with_intent("new_trip")
        .with_delegation("logistics")
        .with_tools(["search_flights"])
        .with_tags(["flights", "simple"])
        .with_response("I will search for round-trip flights from Los Angeles to Miami from July 1 to July 10, 2026.")
        .with_constraints({
            "origin": "LAX",
            "destination": "MIA",
            "start_date": "2026-07-01",
            "end_date": "2026-07-10"
        })
        .build())
    
    print("Task 1 (Builder Pattern):")
    print(task1.to_json())
    print("\n" + "="*50 + "\n")
    
    # Example 2: Loading from dict
    task_dict = {
        "task_id": "ORCH-T8",
        "tier": 2,
        "difficulty": "medium",
        "description": "Mixed input test",
        "category": "orchestrator",
        "input": {
            "type": "mixed",
            "format": "json_plus_nlp",
            "structured_part": {"origin": "SFO", "destination": "TYO"},
            "nlp_query": "I'm interested in temples and anime"
        },
        "expected_output": {
            "intent": "new_trip",
            "updated_constraints": {"origin": "SFO", "destination": "TYO"},
            "delegation": "logistics",
            "response_to_user": "I'll search for flights to Tokyo for you."
        }
    }
    
    task2 = OrchestratorTask.from_dict(task_dict)
    print("Task 2 (From Dict):")
    print(task2.to_json())
