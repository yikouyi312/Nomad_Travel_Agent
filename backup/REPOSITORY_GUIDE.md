# Plan Repository & Evaluation Workflow

## Overview

This system enables you to:
1. **Save** verified plans as JSON (by task_id)
2. **Load** and **evaluate** plans from repository
3. **Track** all saved plans with metadata

## Directory Structure

```
plans/
├── task_123/
│   └── plan.json          # {"metadata": {...}, "plan": {...}}
├── task_456/
│   └── plan.json
└── task_789/
    └── plan.json
```

## Quick Start

### Step 1: Generate & Save a Plan (In notebook)

```python
# Cell 5 now automatically:
# 1. Generates plan via Verifier
# 2. Evaluates with Evaluator
# 3. Saves to plans/{task_id}/plan.json
```

### Step 2: Load & Evaluate by task_id

```python
from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator

# Load plan
repo = PlanRepository(base_dir="plans")
plan = repo.load_plan(task_id="task_123")

# Evaluate it
evaluator = NomadEvaluator()
result = evaluator.evaluate(agent_output=plan, task_id="task_123")

print(f"Score: {result['overall_score']:.1%}")
```

### Step 3: Batch Evaluate All Plans

```python
repo = PlanRepository(base_dir="plans")
evaluator = NomadEvaluator()

# Get all saved task IDs
all_tasks = repo.get_all_plans()

# Evaluate each
for task_id in all_tasks:
    result = evaluator.evaluate_from_repo(task_id=task_id, plan_repo_dir="plans")
    print(f"{task_id}: {result['overall_score']:.1%}")

# Export summary
repo.export_plans_summary("all_results.json")
```

## API Reference

### PlanRepository

#### `save_plan(plan, task_id, save_metadata=True) -> str`
Save a verified plan to JSON.

```python
repo = PlanRepository()
path = repo.save_plan(my_plan_dict, "task_001")
# Creates: plans/task_001/plan.json
```

#### `load_plan(task_id) -> dict`
Load a plan (without metadata).

```python
plan = repo.load_plan("task_001")
```

#### `load_plan_with_metadata(task_id) -> dict`
Load a plan with metadata.

```python
data = repo.load_plan_with_metadata("task_001")
# Returns: {"metadata": {...}, "plan": {...}}
```

#### `get_all_plans() -> list`
Get all task IDs with saved plans.

```python
task_ids = repo.get_all_plans()
# Returns: ["task_001", "task_002", ...]
```

#### `plan_exists(task_id) -> bool`
Check if a plan exists.

```python
if repo.plan_exists("task_001"):
    print("Plan exists!")
```

#### `delete_plan(task_id) -> bool`
Delete a saved plan.

```python
repo.delete_plan("task_001")
```

#### `export_plans_summary(output_file) -> str`
Export summary of all plans to JSON.

```python
repo.export_plans_summary("summary.json")
# Creates: summary.json with metadata for all plans
```

### NomadEvaluator

#### `evaluate(agent_output, task_id=None, hard_constraints=None, expected_tools=None, tool_logs=None) -> dict`
Evaluate a plan directly.

```python
evaluator = NomadEvaluator()
result = evaluator.evaluate(
    agent_output=plan_dict,
    task_id="task_001",
    hard_constraints=["Budget: $3000", "Destination: Paris"]
)
```

#### `evaluate_from_repo(task_id, plan_repo_dir="plans", ...) -> dict`
Evaluate a plan loaded from repository.

```python
evaluator = NomadEvaluator()
result = evaluator.evaluate_from_repo(
    task_id="task_001",
    plan_repo_dir="plans"
)
```

## Workflow

### Standard Workflow (Notebook)

```
Cell 1: Import & Setup
  ↓
Cell 2: Setup State & Constraints
  ↓
Cell 3-5: Specialist → Verifier → Evaluator
  ↓
Cell 5: Automatically saves plan to repository
  ↓
Cell 6: Load and re-evaluate from repository (optional)
```

### Batch Evaluation Workflow

```python
# Step 1: Generate multiple plans (run notebook multiple times)
# - Each run saves a plan with unique task_id

# Step 2: Batch evaluate all plans
from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator

repo = PlanRepository()
evaluator = NomadEvaluator()

results = {}
for task_id in repo.get_all_plans():
    results[task_id] = evaluator.evaluate_from_repo(task_id)

# Step 3: Analyze results
import json
for task_id, result in results.items():
    print(f"{task_id}: {result['overall_score']:.1%}")
```

## Save File Format

Each plan is saved in this format:

```json
{
  "metadata": {
    "task_id": "task_123",
    "saved_at": "2026-03-25T15:30:45.123456",
    "schema_version": "1.0"
  },
  "plan": {
    "task_id": "task_123",
    "is_valid": true,
    "itinerary": {
      "trip_summary": {...},
      "flights": {...},
      "accommodation": {...},
      "activities": [...],
      "cost_breakdown": {...}
    },
    "constraint_validation": {...}
  }
}
```

## Summary Export Format

When you export a summary:

```json
{
  "generated_at": "2026-03-25T15:35:20.654321",
  "total_plans": 3,
  "plans": {
    "task_123": {
      "saved_at": "2026-03-25T15:30:45.123456",
      "destination": "Paris",
      "origin": "New York",
      "duration_nights": 7,
      "total_cost": 2400.50,
      "is_valid": true
    },
    ...
  }
}
```

## Examples

### Example 1: Save and Load

```python
from tools.plan_repository import PlanRepository

repo = PlanRepository()

# Save
my_plan = {...}  # Your verified plan
path = repo.save_plan(my_plan, "paris_trip_001")
print(f"Saved to: {path}")

# Load
loaded = repo.load_plan("paris_trip_001")
assert loaded == my_plan
```

### Example 2: Evaluate by Task ID

```python
from tools.evaluator import NomadEvaluator

evaluator = NomadEvaluator()

# Evaluate directly from repository
result = evaluator.evaluate_from_repo(
    task_id="paris_trip_001",
    plan_repo_dir="plans"
)

print(f"Overall Score: {result['overall_score']:.1%}")
print(f"CSR Score: {result['csr_score']:.1%}")
print(f"Constraint Breakdown:")
for constraint, met in result['constraint_breakdown'].items():
    status = "✓" if met else "✗"
    print(f"  {status} {constraint}")
```

### Example 3: Batch Processing

```python
from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator

repo = PlanRepository()
evaluator = NomadEvaluator()

# Evaluate all saved plans
results = {}
for task_id in repo.get_all_plans():
    print(f"Evaluating {task_id}...")
    result = evaluator.evaluate_from_repo(task_id)
    results[task_id] = result

# Export summary
repo.export_plans_summary("evaluation_results.json")

# Print summary
print("\n=== EVALUATION SUMMARY ===")
for task_id, result in results.items():
    print(f"{task_id}: {result['overall_score']:.1%}")
```

## Tips

1. **Unique task_ids**: Use unique task_ids for each new plan
2. **Metadata**: Automatically includes timestamp and schema version
3. **Multiple evaluations**: Same plan can be evaluated multiple times with different constraints
4. **Batch operations**: Use `get_all_plans()` to process all saved plans
5. **Cleanup**: Use `delete_plan()` to remove old plans and free space

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `FileNotFoundError: Plan not found` | Ensure the task_id exists in plans/ directory |
| Plans not saving | Check write permissions to `plans/` directory |
| Import error: `plan_repository` | Ensure file is in `nomad/src/tools/` directory |
| Can't find evaluator method | Use latest version of `evaluator.py` with relative imports |
