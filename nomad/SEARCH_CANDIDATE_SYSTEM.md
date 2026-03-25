# Search Candidate Retrieval System

## Overview

Specialists now save every search result as **candidates** that can be retrieved later by `task_id` and `category` (flights/hotels/activities). This enables:

- **Result reuse**: Build multiple itineraries from the same search
- **Benchmarking**: Compare specialist outputs across tasks
- **Evaluation**: Analyze what options were available vs. what was selected
- **Alternative scenarios**: Show user different combinations of saved results

## Changes to specialist.py

### Return Type Change

**Before**:
```python
def run_specialist(...) -> str:
    return extract_text(response)

# Usage
draft = run_logistics_specialist(constraints_json, task_id)
```

**After**:
```python
def run_specialist(...) -> Tuple[str, Dict[str, Any]]:
    return extract_text(response), search_results

# Usage
draft, search_results = run_logistics_specialist(constraints_json, task_id)
```

### Automatic Candidate Saving

When you pass `task_id` to a specialist, it automatically:

1. **Intercepts each tool call result**
   - Categorizes by tool name (flight → "flights", hotel → "hotels", etc.)
   - Saves with timestamp and input parameters

2. **Accumulates in local dict**
   - Returns `search_results: {flights: [...], hotels: [...], activities: [...]}`

3. **Persists to disk**
   - Location: `nomad/src/search_candidates/{task_id}/{category}_candidates.json`
   - Format: Array of candidate objects with metadata

## Storage Structure

```
nomad/src/search_candidates/
└── plan_20260325_120000_abcdef/
    ├── flights_candidates.json
    ├── hotels_candidates.json
    └── activities_candidates.json

# Example file format (flights_candidates.json)
[
  {
    "task_id": "plan_20260325_120000_abcdef",
    "category": "flights",
    "timestamp": "2026-03-25T12:00:45.123456",
    "tool_name": "search_flights",
    "tool_input": {
      "origin": "New York",
      "destination": "Seattle",
      "date": "2026-05-05",
      "round_trip": true
    },
    "tool_result": [
      {
        "airline": "Delta",
        "departure": "08:00 AM",
        "arrival": "01:30 PM",
        "price": 450,
        "duration": "5h 30m"
      },
      {
        "airline": "United",
        "departure": "02:00 PM",
        "arrival": "08:45 PM",
        "price": 380,
        "duration": "6h 15m"
      }
    ]
  }
]
```

## API Reference

### `run_specialist(task_description, tools, constraints_json, task_id=None)`

**Returns**: `Tuple[str, Dict[str, Any]]`

```python
draft_text, search_results = run_specialist(
    task_description="Find flights",
    tools=LOGISTICS_TOOLS,
    constraints_json=constraints,
    task_id="plan_20260325_120000"  # <-- Optional but enables saving
)

# draft_text: Final itinerary text
# search_results: {"flights": [...], "hotels": [...], "activities": [...]}
```

If `task_id` is not provided, candidates are NOT saved to disk (but still returned in search_results).

### `run_logistics_specialist(constraints_json, task_id=None)`

**Returns**: `Tuple[str, Dict[str, Any]]`

```python
draft, searches = run_logistics_specialist(
    constraints_json=constraints,
    task_id=state.task_id
)

# searches contains: flights and hotels candidates
```

### `run_activities_specialist(constraints_json, task_id=None)`

**Returns**: `Tuple[str, Dict[str, Any]]`

```python
draft, searches = run_activities_specialist(
    constraints_json=constraints,
    task_id=state.task_id
)

# searches contains: activities candidates
```

### `retrieve_candidates(task_id, category=None)`

**Purpose**: Load saved candidates from disk

**Returns**: `Dict[category -> List[candidate]]`

```python
# Get all candidates for a task
all_candidates = retrieve_candidates("plan_20260325_120000")
# Returns: {"flights": [...], "hotels": [...], "activities": [...]}

# Get specific category only
flights_only = retrieve_candidates("plan_20260325_120000", category="flights")
# Returns: {"flights": [...]}

# Get single item
flights_list = flights_only.get("flights", [])
first_flight_option = flights_list[0]  # Contains all search results from that tool call
```

### `list_candidate_tasks()`

**Purpose**: List all task IDs that have saved candidates

**Returns**: `List[str]`

```python
task_ids = list_candidate_tasks()
# Returns: ["plan_20260325_120000", "plan_20260325_115530", ...]
```

## Integration with Verifier

The updated flow now looks like:

```python
# Main.py workflow
state = TravelState()

# Run specialists with task_id
logistics_draft, logistics_searches = run_logistics_specialist(constraints_str, task_id=state.task_id)
activities_draft, activities_searches = run_activities_specialist(constraints_str, task_id=state.task_id)

# Merge search results
all_searches = {
    "flights": logistics_searches.get("flights", []),
    "hotels": logistics_searches.get("hotels", []),
    "activities": activities_searches.get("activities", [])
}

# Pass to verifier for blueprint generation
verification = verify_and_format_itinerary(
    full_draft,
    constraints_str,
    task_id=state.task_id,
    search_results=all_searches  # <-- Both verifier AND candidates now have this
)
```

## Use Cases

### 1. Alternative Itineraries

```python
# User didn't like first itinerary, show alternatives

# Load candidates from previous search
candidates = retrieve_candidates("plan_20260325_120000")

# Build different combinations:
# Itinerary A: flights[0], hotels[0], activities[0:2]
# Itinerary B: flights[1], hotels[1], activities[2:4]
# etc.
```

### 2. Benchmark Analysis

```python
# Evaluate specialist performance across tasks

for task_id in ["T1-01", "T1-02", "T1-03"]:
    candidates = retrieve_candidates(task_id)
    
    # Analyze: How many options were found?
    # How good were they? (based on later verification)
```

### 3. Cost Comparison

```python
# Analyze which flights/hotels were cheapest in candidates

flights = retrieve_candidates(task_id, "flights")["flights"]

for candidate in flights:
    # candidate["tool_result"] is list of flights from that API call
    avg_price = sum(f["price"] for f in candidate["tool_result"]) / len(candidate["tool_result"])
    print(f"Average flight price from {candidate['timestamp']}: ${avg_price}")
```

### 4. A/B Testing

```python
# Compare search results across different constraint variations

tasks = ["baseline", "budget_tight", "flexible_dates"]

for task_name in tasks:
    task_id = retrieve_task_by_name(task_name)
    candidates = retrieve_candidates(task_id)
    
    flight_count = sum(len(c["tool_result"]) for c in candidates["flights"])
    hotel_count = sum(len(c["tool_result"]) for c in candidates["hotels"])
    
    print(f"{task_name}: {flight_count} flights, {hotel_count} hotels")
```

## File Structure

```
nomad/src/
├── agents/
│   ├── specialist.py (MODIFIED)
│   ├── specialist_retrieval_example.py (NEW)
│   ├── verifier.py
│   └── ...
├── search_candidates/ (NEW)
│   ├── plan_20260325_120000/
│   │   ├── flights_candidates.json
│   │   ├── hotels_candidates.json
│   │   └── activities_candidates.json
│   └── plan_20260325_115530/
│       ├── flights_candidates.json
│       └── ...
└── verification_results/
    └── (existing structure, unchanged)
```

## Next Steps

### In main.py

Update the specialist calls to handle the new return type:

```python
# OLD
logistics_draft = run_logistics_specialist(constraints_str, task_id)

# NEW
logistics_draft, logistics_searches = run_logistics_specialist(constraints_str, task_id)

# And merge all searches before passing to verifier
all_searches = merge_search_results(logistics_searches, activities_searches)
```

### Integration Points

1. **Specialists → Candidates**: ✅ DONE (auto-save when task_id provided)
2. **Candidates → Verifier**: ⏳ TODO (update main.py to merge and pass)
3. **Candidates → Evaluation**: ⏳ TODO (create evaluation pipeline using retrieve_candidates)
4. **Candidates → UI**: ⏳ TODO (show user alternative combinations)

## Token Consideration

- **Saved candidates**: Can be large (full search result list × multiple API calls)
- **Reuse benefit**: Avoid re-running API calls for alternative itineraries
- **Trade-off**: Storage (disk space) vs. Time (no re-calling APIs)

For benchmark tasks with limited variation, this is highly efficient.

## Example Code

See `specialist_retrieval_example.py` for:
- How to save candidates (automatic during specialist run)
- How to retrieve candidates by task_id and category
- How to build alternative scenarios from candidates
- How to perform cross-task analysis
