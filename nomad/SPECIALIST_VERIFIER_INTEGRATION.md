# Using Specialist with Verifier Integration

## 📊 New Return Format

`run_logistics_specialist()` and `run_activities_specialist()` now return **3 values** (instead of 2):

```python
draft_text, search_results, verifier_context = run_logistics_specialist(
    constraints_str,
    task_id=state.task_id
)
```

### Return Value Structure

#### 1. **draft_text** (str)
The final itinerary text summary from the specialist.

```
Example:
"Based on my search, I recommend:
- Outbound: Delta DL123 departing 8:00 AM, arriving 1:30 PM ($450)
- Return: United UA456 departing 2:00 PM, arriving 8:45 PM ($380)
- Hotel: Pike Place Hotel, 7 nights @ $200/night ($1400)
Total Cost: $2,230"
```

#### 2. **search_results** (Dict[str, List])
Dictionary containing all search results accumulated during specialist execution.

```python
search_results = {
    "flights": [
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
    ],
    "hotels": [
        {
            "name": "Pike Place Hotel",
            "address": "123 Pike St, Seattle, WA",
            "price_per_night": 200,
            "rating": 4.5
        }
    ],
    "activities": []
}
```

#### 3. **verifier_context** (Dict[str, Any]) - NEW!
Rich context about the specialist's search process and analysis for the verifier stage.

```python
verifier_context = {
    # What the specialist was thinking/analyzing
    "specialist_reasoning": [
        "Searching for flights that match the date range May 5-12",
        "Found 2 good flight options within budget",
        "Prioritizing direct flights over connections"
    ],
    
    # How many of each type were found
    "search_coverage": {
        "flights": 5,      # Total flight options found
        "hotels": 3,       # Total hotel options found
        "activities": 0    # No activities needed for this search
    },
    
    # Total options discovered
    "total_searches": 8,
    
    # Key decisions made during search
    "key_decisions": [
        "Selected Delta as primary carrier (best price)",
        "Chose Pike Place Hotel (best rating)"
    ],
    
    # Budget analysis
    "budget_analysis": "Total cost $2,230 is within $3000 budget",
    
    # Any concerns identified
    "risk_factors": [
        "Limited hotel options in budget",
        "Return flight has 1-hour layover"
    ],
    
    # Verifier recommendation
    "recommendations": "Itinerary meets all constraints and is recommended",
    
    # Summary of tool calls made
    "tool_calls_summary": [
        {
            "tool": "search_flights",
            "category": "flights",
            "result_count": 5,
            "turn": 1
        },
        {
            "tool": "search_hotels",
            "category": "hotels",
            "result_count": 3,
            "turn": 2
        }
    ],
    
    # The draft text (for reference)
    "final_draft": "...",
    
    # Error flag if specialist failed
    "error": None
}
```

## 🔄 Workflow: How to Use for Verifier Stage

### Step 1: Call Specialist and Unpack Returns

```python
# Run logistics specialist
logistics_draft, logistics_searches, logistics_context = run_logistics_specialist(
    constraints_str=state.constraints.model_dump_json(indent=2),
    task_id=state.task_id  # Important: enables candidate saving
)

# Similarly for activities
activities_draft, activities_searches, activities_context = run_activities_specialist(
    constraints_str=state.constraints.model_dump_json(indent=2),
    task_id=state.task_id
)
```

### Step 2: Accumulate Results by Category

```python
# Merge search results from both specialists
all_search_results = {
    "flights": logistics_searches.get("flights", []),
    "hotels": logistics_searches.get("hotels", []),
    "activities": activities_searches.get("activities", [])
}

# Store specialist contexts for reference
specialist_contexts = {
    "logistics": logistics_context,
    "activities": activities_context
}
```

### Step 3: Review Specialist Analysis (Optional)

```python
# Before sending to verifier, you can inspect specialist reasoning:

print("Logistics Coverage:", logistics_context["search_coverage"])
# Output: {'flights': 5, 'hotels': 3, 'activities': 0}

print("Logistics Reasoning:", logistics_context["specialist_reasoning"])
# Output: ["Searching for flights...", "Found 2 good options...", ...]

print("Key Decisions:", logistics_context["key_decisions"])
# Output: ["Selected Delta as primary carrier", ...]

print("Risk Factors:", logistics_context["risk_factors"])
# Output: ["Limited hotel options", ...]
```

### Step 4: Pass to Verifier

```python
# Combine all drafts
full_draft = "\n\n".join([
    f"--- LOGISTICS ---\n{logistics_draft}",
    f"--- ACTIVITIES ---\n{activities_draft}"
])

# Call verifier with search results
# (Verifier now has full context)
verification = verify_and_format_itinerary(
    draft_text=full_draft,
    constraints_json=state.constraints.model_dump_json(indent=2),
    task_id=state.task_id,
    search_results=all_search_results  # <-- Full search options
)
```

### Step 5: Verifier Makes Final Decision

The verifier now has:
- ✅ Full draft from specialist
- ✅ All search options (for determining which was selected)
- ✅ Specialist reasoning (context for validation)
- ✅ Task ID (for tracking)

Verifier uses this to output:
- Blueprint with selection references (flight_0, hotel_0, etc.)
- Validation status
- Final recommendation

## 📈 Example: Complete Flow

```python
# Initialize
state = TravelState()
constraints_str = state.constraints.model_dump_json(indent=2)

# Step 1: Run specialists (get three values each)
logistics_draft, logistics_searches, logistics_ctx = run_logistics_specialist(
    constraints_str,
    task_id=state.task_id
)

activities_draft, activities_searches, activities_ctx = run_activities_specialist(
    constraints_str,
    task_id=state.task_id
)

# Step 2: Accumulate
print("=" * 60)
print("SPECIALIST ANALYSIS")
print("=" * 60)

print(f"\n🔍 Logistics Specialist:")
print(f"  - Flights found: {logistics_ctx['search_coverage']['flights']}")
print(f"  - Hotels found: {logistics_ctx['search_coverage']['hotels']}")
print(f"  - Reasoning: {logistics_ctx['specialist_reasoning'][0]}")

print(f"\n🎯 Activities Specialist:")
print(f"  - Activities found: {activities_ctx['search_coverage']['activities']}")

# Step 3: Merge all results
all_searches = {**logistics_searches, **activities_searches}

# Step 4: Send to verifier
verification = verify_and_format_itinerary(
    logistics_draft + "\n\n" + activities_draft,
    constraints_str,
    task_id=state.task_id,
    search_results=all_searches
)

# Step 5: Display result
print("\n" + "=" * 60)
print("FINAL RECOMMENDATION")
print("=" * 60)
print(f"Valid: {verification['is_valid']}")
print(f"Blueprint: {verification['itinerary_blueprint']}")
print(f"Message: {verification['final_message_to_user']}")
```

## 🎯 Key Benefits

| Aspect | Benefit |
|--------|---------|
| **Specialist Reasoning** | Verifier understands why specialist chose these options |
| **Search Coverage** | Verifier knows how many alternatives were considered |
| **Risk Factors** | Verifier can flag concerns identified by specialist |
| **Audit Trail** | Tool calls logged for later analysis |
| **Candidate Persistence** | All options saved by task_id for alternative scenarios |
| **Smart Validation** | Verifier can validate selection against available options |

## 💡 Using Specialist Context for Decisions

```python
# Example: Check if specialist found enough options

if logistics_ctx["search_coverage"]["flights"] < 3:
    print("⚠️ Warning: Only {count} flights found".format(
        count=logistics_ctx["search_coverage"]["flights"]
    ))
    print("→ Constraint may need relaxation")

# Example: Identify risk factors

if logistics_ctx["risk_factors"]:
    print("⚠️ Specialist identified concerns:")
    for risk in logistics_ctx["risk_factors"]:
        print(f"  - {risk}")

# Example: Use specialist recommendation

print(f"💡 Specialist recommendation: {logistics_ctx['recommendations']}")
```

## 🔗 Integration Points

### With Candidates System
Candidates are auto-saved when `task_id` is provided:
- Location: `search_candidates/{task_id}/{category}_candidates.json`
- Contains: Full tool inputs + outputs + metadata

### With Verification System
Verification blueprint auto-saved when `search_results` provided:
- Location: `verification_results/{task_id}_verification.json`
- Contains: Blueprint + search_results for later expansion

### With Evaluation Pipeline
All three components (candidates, verification, specialist_context) enable:
- Benchmarking specialist coverage
- Comparing search strategies
- Analyzing selection quality
- A/B testing constraints

## Usage in Notebooks

See `agent_test.ipynb` for complete working example with:
1. Unpacking 3-value returns
2. Viewing specialist context
3. Accumulating search results
4. Passing to verifier
5. Displaying final blueprint

## Error Handling

```python
try:
    draft, searches, context = run_logistics_specialist(constraints_str, task_id)
    
    # Check for errors
    if context.get("error"):
        print(f"⚠️ Specialist Error: {context['error']}")
        # Verifier will still run, but with incomplete data
    
except Exception as e:
    print(f"❌ Specialist Failed: {e}")
    # Create empty placeholder for verifier
    draft = "Unable to generate itinerary"
    searches = {"flights": [], "hotels": [], "activities": []}
    context = {"error": str(e)}
```

## Summary

**Old way:**
```python
draft = run_logistics_specialist(constraints_str)
# Only had the draft text, no insight into specialist's analysis
```

**New way:**
```python
draft, searches, context = run_logistics_specialist(constraints_str, task_id)
# Have draft + all search options + specialist reasoning
# Can make intelligent validation decisions in verifier
# Can build alternatives from saved candidates
```
