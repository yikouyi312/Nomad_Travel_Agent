# Orchestrator Task Format Guide

## Overview

This JSON task format is used to define and evaluate various scenarios for the Orchestrator component. Each task follows the expected output format of `ORCHESTRATOR_ANALYSIS_SCHEMA`.

## Task Structure

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique identifier (format: ORCH-T{number}) |
| `tier` | integer | Difficulty tier (1-3) |
| `difficulty` | string | Difficulty level (easy, medium, hard) |
| `description` | string | Brief task description |
| `category` | string | Fixed value: "orchestrator" |
| `input` | object | Input data |
| `expected_output` | object | Expected output (matching SCHEMA) |

### Input Formats

#### 1. Structured JSON Input
```json
{
  "input": {
    "type": "structured",
    "format": "json",
    "content": {
      "origin": "BOS",
      "destination": "SEA",
      "start_date": "2026-05-05",
      "end_date": "2026-05-12"
    }
  }
}
```

#### 2. Mixed Input (JSON + NLP)
```json
{
  "input": {
    "type": "mixed",
    "format": "json_plus_nlp",
    "structured_part": {
      "origin": "NYC",
      "destination": "PAR"
    },
    "nlp_query": "Also, I love museums and French cuisine"
  }
}
```

#### 3. Pure Natural Language Input
```json
{
  "input": {
    "type": "natural_language",
    "format": "text",
    "content": "I want to go to Tokyo in October"
  }
}
```

### Expected Output Format

Must conform to `ORCHESTRATOR_ANALYSIS_SCHEMA`:

```json
{
  "intent": "new_trip|update_constraints|ask_question|confirm_itinerary",
  "updated_constraints": {
    "origin": "string",
    "destination": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "budget_usd": "number",
    "num_travelers": "integer",
    "dietary_needs": ["array"],
    "interests": ["array"]
  },
  "delegation": "logistics|activities|both|none",
  "response_to_user": "string"
}
```

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `current_state_constraints` | object | Current state for constraint updates |
| `expected_tools` | array | List of expected tools to be called |
| `tags` | array | Task tags (flights, hotels, activities, etc.) |

## Intent Types

- **new_trip**: User initiates a new travel plan
- **update_constraints**: User modifies existing constraints
- **ask_question**: User asks a general question without planning a trip
- **confirm_itinerary**: User confirms their itinerary

## Delegation Types

- **logistics**: Requires searching for flights, hotels, and travel information
- **activities**: Requires searching for activities, restaurants, and entertainment
- **both**: Requires both logistics and activity searches
- **none**: No specialist delegation needed

## Difficulty Tiers

- **Tier 1 (Easy)**: Single clear JSON input or simple questions
- **Tier 2 (Medium)**: Mixed input (JSON+NLP) or multiple constraints
- **Tier 3 (Hard)**: Constraint updates, complex logic, or multi-level reasoning

## Usage Examples

### Creating a New Benchmark Task

```python
import json

task = {
    "task_id": "ORCH-T6",
    "tier": 2,
    "difficulty": "medium",
    "description": "Hotel search with budget constraint",
    "category": "orchestrator",
    
    "input": {
        "type": "structured",
        "format": "json",
        "content": {
            "destination": "LON",
            "start_date": "2026-06-01",
            "end_date": "2026-06-07",
            "budget_usd": 3000,
            "num_travelers": 1
        }
    },
    
    "expected_output": {
        "intent": "new_trip",
        "updated_constraints": {
            "destination": "LON",
            "start_date": "2026-06-01",
            "end_date": "2026-06-07",
            "budget_usd": 3000,
            "num_travelers": 1
        },
        "delegation": "logistics",
        "response_to_user": "I will search for flights and hotels in London from June 1 to June 7, 2026 for 1 traveler with a budget of $3000."
    },
    
    "expected_tools": ["search_hotels"],
    "tags": ["hotels", "budget", "single_traveler"]
}

# Save to file
with open('new_task.json', 'w') as f:
    json.dump(task, f, indent=2)
```

### Running Tasks Through the Test Framework

```python
from nomad_benchmark.src.evaluator import evaluate_orchestrator

task = load_task("ORCH-T6")
result = evaluate_orchestrator(task)
print(f"Pass: {result['passed']}")
print(f"Score: {result['score']}")
```

## Constraint Field Reference

| Field | Type | Description |
|-------|------|-------------|
| origin | string | Departure airport code (e.g., BOS, NYC) |
| destination | string | Destination airport code (e.g., SEA, PAR) |
| start_date | string | Departure date (YYYY-MM-DD) |
| end_date | string | Return date (YYYY-MM-DD) |
| budget_usd | number | Total budget in USD |
| num_travelers | integer | Number of travelers |
| dietary_needs | array | Dietary requirements (e.g., vegetarian, vegan) |
| interests | array | Interests (e.g., museums, food) |

## Best Practices

1. **One Task, One Scenario** - Each task should focus on a single user interaction pattern
2. **Clear Expected Output** - The `expected_output` field must be completely filled
3. **Appropriate Difficulty Level** - Ensure tier and difficulty are well-matched
4. **Meaningful Tags** - Use tags for easy task categorization and statistics
5. **Real-World Use Cases** - Design tasks based on actual user queries and interactions
