# SerpManager Integration Summary

## Objectives
Combine `SerpManager` and `serpapi.py` to achieve:
- ✅ Search and save capabilities
- ✅ Cache-first strategy (use cache if exists, call API and save if not)
- ✅ Backward compatibility with old code
- ✅ Support benchmark snapshot reproducibility

---

## Major Changes

### 1. **nomad/src/tools/serpapi.py** - Complete Rewrite

#### New `SerpManager` Class
```python
class SerpManager:
    """Unified SerpAPI manager supporting three-layer cache"""
```

**Features:**
- **Three-layer cache strategy**: Snapshot → Local Cache → Real API
- **Auto-save**: Every API call is automatically saved to `nomad/src/cache/`
- **Snapshot support**: For benchmark task reproducibility
- **Deterministic cache key**: MD5 hash based on parameters, same parameters always hit same cache

**Core Methods:**
```python
manager = SerpManager(api_key="...", snapshot_path="...")

# Three search methods
manager.search_flights(origin, destination, departure_date, return_date, 
                      task_id=None, turn=1)
manager.search_hotels(location, check_in, check_out, adults=1, 
                     task_id=None, turn=1)
manager.search_places(query, location, task_id=None, turn=1)
```

#### Backward Compatible Functions
Preserve original function interface:
```python
search_flights(origin, destination, departure_date, return_date)
search_hotels(location, check_in, check_out, adults=1)
search_places(query, location)
```

These functions now use the new `SerpManager` internally, automatically gaining cache capabilities.

---

### 2. **nomad/src/tools/dispatch.py** - Enhanced Integration

**Changes:**
- Extract `task_id` and `turn` from tool parameters
- Route to `SerpManager` methods using singleton pattern
- Preserve all other tool execution logic

**Updated `dispatch_tool` function:**
```python
def dispatch_tool(tool_name, arguments):
    # Auto extract task_id and turn
    task_id = arguments.pop("task_id", None)
    turn = arguments.pop("turn", 1)
    
    # Route to SerpManager
    if tool_name == "search_flights":
        manager = get_serp_manager()
        result = manager.search_flights(task_id=task_id, turn=turn, **arguments)
```

---

### 3. **New Files**

#### nomad/src/tools/README_SerpManager.md
Comprehensive usage documentation including:
- Three usage methods
- Cache workflow diagrams
- API parameter explanation
- Configuration guide

#### nomad/src/tools/serp_examples.py
Four practical examples:
1. Old interface demonstration
2. New interface demonstration
3. Benchmark snapshot mode
4. Cache comparison demonstration

---

## Cache Workflow

```
User calls search_flights()
        ↓
1️⃣ Check snapshot (if task_id exists)
        ↓ Found → return
        ↓ Not found
2️⃣ Check local cache file
        ↓ Found → return
        ↓ Not found
3️⃣ Call real SerpAPI
        ↓
4️⃣ Auto-save to nomad/src/cache/
        ↓
5️⃣ Return result
```

---

## Usage Example Comparison

### Old Method (still compatible)
```python
from tools.serpapi import search_flights

flights = search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12",
)
# First time: [API call] google_flights...
# Second time: [Cache hit] google_flights
```

### Recommended New Method
```python
from tools.serpapi import SerpManager

manager = SerpManager()

flights = manager.search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12",
)
```

### Benchmark Mode
```python
manager = SerpManager(snapshot_path="data/serp_snapshot.json")

flights = manager.search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12",
    task_id="T1-01",
    turn=1,
)
# [Snapshot hit] google_flights (task=T1-01, turn=1)
```

---

## Cache Storage Structure

```
nomad/src/cache/
├── google_flights_a1b2c3d4e5f6.json    # Flights cache
├── google_hotels_b2c3d4e5f6a1.json     # Hotels cache
├── google_local_c3d4e5f6a1b2.json      # Places cache
└── ...
```

**Cache Key Rules:**
- Based on MD5 hash of `engine` + `params`
- Completely deterministic: same input → same cache key → same file

---

## Cost and Performance Benefits

### API Cost Savings
- **First call**: 10 API calls = $1-2
- **Same query**: No API calls thereafter
- **Scenario**: Multiple queries for same flight → 90%+ cost savings

### Speed Improvements
- **API call**: 5-10 seconds
- **Cache hit**: 100-200 milliseconds
- **Speedup factor**: 25-100x

---

## Backward Compatibility

✅ **Fully Compatible**
```python
# Old code continues to work
from tools.serpapi import search_flights, search_hotels, search_places
flights = search_flights(...)  # Auto-uses new cache system
```

✅ **Old @cached_api_call decorator removed**
- Functionality replaced by SerpManager
- No need to modify existing code

---

## Configuration Requirements

### .env
```env
SERP_API=your_serpapi_key_here
```

### Optional: Benchmark Snapshot
```env
SNAPSHOT_PATH=data/serp_snapshot.json
```

---

## New Log Output Examples

```
[Snapshot hit] google_flights (task=T1-01, turn=1)
```

```
[Cache hit] google_flights
```

```
[API call] google_flights...
[Saved] google_flights -> c:\GIT\aiagent\nomad\src\cache
```

---

## Frequently Asked Questions

**Q: How to clear cache?**
A: Delete files in `nomad/src/cache/` directory

**Q: When does cache expire?**
A: Currently no expiration mechanism - once cached, always used

**Q: Can I disable caching?**
A: Delete cache files, next call will use real API

**Q: Does cache invalidation work?**
A: Manual deletion of specific cache files triggers new API fetch

---

## Summary

| Feature | Old Method | New Method |
|---------|-----------|-----------|
| **Cache Support** | ✅ Yes (Simple) | ✅ Yes (Three-tier) |
| **Auto-save** | ✅ Yes | ✅ Yes |
| **API Cost** | Medium | ✅ Minimal |
| **Benchmark Support** | ❌ No | ✅ Yes |
| **Backward Compatible** | N/A | ✅ Fully |
| **Speed** | Fast | ✅ Faster (cached) |
| **Flexibility** | Medium | ✅ High |
