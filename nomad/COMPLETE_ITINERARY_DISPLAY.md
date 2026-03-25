# Complete Itinerary Display Feature

## 🎯 Overview

Now `verify_and_format_itinerary()` automatically returns a **complete itinerary** with all details when `search_results` are provided. This means you get both:

1. **Lightweight Blueprint** - For efficient storage/transmission
   ```python
   {
     "flights": {"outbound_ref": "flight_0", "return_ref": "flight_1"},
     "hotels": {"hotel_ref": "hotel_0", ...},
     "activities": [...],
     "estimated_cost": 2435
   }
   ```

2. **Complete Itinerary** - With full details expanded
   ```python
   {
     "flights": {
       "outbound": {"airline": "Delta", "departure": "08:00 AM", ...},
       "return": {"airline": "United", "departure": "02:00 PM", ...}
     },
     "hotels": {
       "name": "Pike Place Hotel",
       "address": "123 Pike St, Seattle, WA",
       "price_per_night": 200,
       "check_in": "2026-05-05",
       "check_out": "2026-05-12",
       "nights": 7
     },
     "activities": [...]
   }
   ```

## 📊 Return Value Structure

```python
verification = verify_and_format_itinerary(
    draft_text,
    constraints_json,
    task_id=state.task_id,
    search_results=all_search_results  # ← Enables complete itinerary
)

# Result contains:
{
  "is_valid": bool,                              # Validation status
  "issues": [...],                               # Any constraint violations
  "itinerary_blueprint": {...},                  # Lightweight refs (flight_0, hotel_0)
  "complete_itinerary": {...},                   # NEW: Full details
  "final_message_to_user": str                   # Summary message
}
```

## 🎨 Display Formatted Itinerary

Use `format_complete_itinerary()` to display nicely formatted trip details:

```python
from agents.verifier import format_complete_itinerary

verification = verify_and_format_itinerary(...)

# Get formatted display string
formatted_text = format_complete_itinerary(verification)
print(formatted_text)
```

**Output Example:**
```
======================================================================
✈️  COMPLETE TRAVEL ITINERARY
======================================================================

✅ STATUS: APPROVED

----------------------------------------------------------------------
✈️  FLIGHTS
----------------------------------------------------------------------

OUTBOUND FLIGHT:
  • airline: Delta
  • departure: 08:00 AM
  • arrival: 01:30 PM
  • price: 450
  • duration: 5h 30m

RETURN FLIGHT:
  • airline: United
  • departure: 02:00 PM
  • arrival: 08:45 PM
  • price: 380
  • duration: 6h 15m

----------------------------------------------------------------------
🏨 HOTELS
----------------------------------------------------------------------
  • name: Pike Place Hotel
  • address: 123 Pike St, Seattle, WA
  • rating: 4.5

  CHECK-IN:  2026-05-05
  CHECK-OUT: 2026-05-12
  DURATION:  7 nights

----------------------------------------------------------------------
🎯 ACTIVITIES & DINING
----------------------------------------------------------------------

Day - 2026-05-05:
  • name: Space Needle Tour
  • price: 25
  • duration: 2 hours

Day - 2026-05-07:
  • name: Pike Place Market Visit
  • price: 0
  • duration: 3 hours

----------------------------------------------------------------------
💰 COST SUMMARY
----------------------------------------------------------------------
  Total Estimated Cost: $2,435.00

======================================================================
📝 Itinerary valid - 7-day Seattle trip within budget
======================================================================
```

## 🔄 Complete Workflow

### Step 1: Run Specialists

```python
logistics_draft, logistics_searches, logistics_ctx = run_logistics_specialist(
    constraints_str,
    task_id=state.task_id
)

activities_draft, activities_searches, activities_ctx = run_activities_specialist(
    constraints_str,
    task_id=state.task_id
)
```

### Step 2: Accumulate Results

```python
all_search_results = {
    "flights": logistics_searches.get("flights", []),
    "hotels": logistics_searches.get("hotels", []),
    "activities": activities_searches.get("activities", [])
}
```

### Step 3: Call Verifier with Search Results

```python
# Important: Pass search_results to enable complete itinerary expansion
verification = verify_and_format_itinerary(
    full_draft,
    constraints_str,
    task_id=state.task_id,
    search_results=all_search_results  # ← Critical for complete details
)
```

### Step 4: Display Complete Itinerary

```python
if verification.get("is_valid"):
    # Option A: Use formatted display
    formatted = format_complete_itinerary(verification)
    print(formatted)
    
    # Option B: Access complete details directly
    complete = verification.get("complete_itinerary")
    print(f"Flights: {complete['flights']}")
    print(f"Hotels: {complete['hotels']}")
    print(f"Activities: {complete['activities']}")
    print(f"Total Cost: ${complete['estimated_cost']:,.2f}")
```

## 📝 Complete Itinerary Structure

### Flights Object

```python
{
  "outbound": {
    "airline": str,
    "departure": str,
    "arrival": str,
    "price": float,
    "duration": str,
    ...  # All fields from search result
  },
  "return": { ... }  # Same structure as outbound
}
```

### Hotels Object

```python
{
  "name": str,
  "address": str,
  "rating": float,
  "price_per_night": float,
  "check_in": str (YYYY-MM-DD),
  "check_out": str (YYYY-MM-DD),
  "nights": int,
  ...  # All fields from search result
}
```

### Activities Array

```python
[
  {
    "name": str,
    "date": str (YYYY-MM-DD),
    "price": float,
    "duration": str,
    ...  # All fields from search result
  },
  ...
]
```

### Cost Summary

```python
{
  "estimated_cost": float,  # Total trip cost
  "flights": {
    "outbound": float,      # Outbound flight cost
    "return": float         # Return flight cost
  },
  "hotels": {
    "total": float,         # Hotel total (price_per_night × nights)
    "per_night": float
  },
  "activities": {
    "total": float          # Activities total cost
  }
}
```

## 🎯 Key Features

✅ **Automatic Expansion**
- Blueprint refs automatically expanded to full details
- No manual `determine_details()` call needed
- Happens transparently in verifier

✅ **Complete Information**
- All original search fields preserved
- Dates, prices, ratings, descriptions included
- Ready for display to users

✅ **Formatted Display**
- Professional, emoji-enhanced output
- Clear sections for flights, hotels, activities
- Cost summary included
- Validation status displayed

✅ **Saved to Disk**
- Complete itinerary stored in `{task_id}_verification.json`
- Enables later retrieval and analysis
- No need to re-search for details

## 💡 Usage Examples

### Example: Show Trip to User

```python
def show_trip_to_user(verification):
    if verification.get("is_valid"):
        print(format_complete_itinerary(verification))
    else:
        print("Trip cannot be approved due to constraint violations")
```

### Example: Build Cost Report

```python
def generate_cost_report(verification):
    complete = verification.get("complete_itinerary")
    
    print(f"Flight Cost: ${complete['flights']['outbound']['price'] + complete['flights']['return']['price']}")
    print(f"Hotel Cost: ${complete['hotels']['price_per_night'] * complete['hotels']['nights']}")
    
    activities_cost = sum(a.get('price', 0) for a in complete['activities'])
    print(f"Activities Cost: ${activities_cost}")
    
    print(f"TOTAL: ${complete['estimated_cost']}")
```

### Example: Save Trip to PDF (future)

```python
def save_trip_to_pdf(verification, filename):
    formatted = format_complete_itinerary(verification)
    
    # Could use reportlab or similar to create PDF
    # from reportlab.pdfgen import canvas
    # ... generate PDF ...
```

## 🔗 Integration Points

| Component | Purpose |
|-----------|---------|
| **Specialist** | Collects search results |
| **Verifier** | Validates + auto-expands blueprint |
| **Storage** | Saves complete details to disk |
| **Display** | `format_complete_itinerary()` for UI |
| **API** | Returns both blueprint and complete details |

## ⚠️ Important Notes

### Search Results Required

Complete itinerary will be `None` if `search_results` not provided:

```python
# ❌ Will have complete_itinerary = None
verification = verify_and_format_itinerary(draft, constraints)

# ✅ Will have complete details
verification = verify_and_format_itinerary(
    draft, 
    constraints,
    search_results=searches  # Enables expansion
)
```

### Memory Consideration

Complete itinerary can be large (due to expanded details):
- Blueprint: ~1-5 KB
- Complete: ~10-50 KB (depending on activity count)

For high-volume scenarios, you may want to:
- Use blueprint-only (omit search_results)
- Compress complete_itinerary before saving
- Archive old results periodically

## 🎓 Example from agent_test.ipynb

See the notebook for complete working example showing:
1. Running specialists with search tracking
2. Passing search_results to verifier
3. Accessing complete_itinerary from result
4. Formatting with `format_complete_itinerary()`
5. Displaying structured trip information

## Summary

| Aspect | Old Way | New Way |
|--------|---------|---------|
| **Details Access** | Call `determine_details()` | Auto-included in result |
| **Display** | Manual formatting | `format_complete_itinerary()` |
| **Token Usage** | Blueprint only (~150 tokens) | +Complete details (~400 tokens) |
| **User Experience** | Lightweight | Complete, formatted trip |
| **Storage** | Blueprint + candidates | Blueprint + complete + candidates |
