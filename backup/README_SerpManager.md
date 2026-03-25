# SerpManager Integration Guide

## Overview

The new `SerpManager` combines caching and API calls together, supporting a three-layer cache strategy:

1. **Snapshot** - For benchmark reproducibility, highest priority
2. **Local Cache** - Automatically cache all API call results
3. **Real-time API Call** - If the first two layers miss, call the real API

## Usage Examples

### Method 1: Using Old Interface (Backward Compatible)

```python
from tools.serpapi import search_flights, search_hotels, search_places

# Call directly, auto-use cache
flights = search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12"
)

hotels = search_hotels(
    location="Seattle, Washington",
    check_in="2026-05-05",
    check_out="2026-05-12"
)

places = search_places(
    query="vegetarian restaurants",
    location="Seattle, Washington"
)
```

### Method 2: Using New SerpManager (Recommended)

```python
from tools.serpapi import SerpManager

# Initialize manager
manager = SerpManager(api_key="your_api_key")

# Search flights
flights = manager.search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12"
)

# Search hotels
hotels = manager.search_hotels(
    location="Seattle, Washington",
    check_in="2026-05-05",
    check_out="2026-05-12",
    adults=1
)

# Search places
places = manager.search_places(
    query="museums",
    location="Seattle, Washington"
)
```

### Method 3: For Benchmark (With Snapshot Support)

```python
from tools.serpapi import SerpManager

# Use snapshot mode, ensure benchmark reproducibility
manager = SerpManager(
    api_key="your_api_key",
    snapshot_path="data/serp_snapshot.json"
)

# Use task_id and turn parameters, auto-prioritize snapshot
flights = manager.search_flights(
    origin="BOS",
    destination="SEA",
    departure_date="2026-05-05",
    return_date="2026-05-12",
    task_id="T1-01",
    turn=1
)
```

## Cache Workflow

```
1. Input search request
        ↓
2. Check snapshot (if task_id provided)
        ↓ Hit → Return
        ↓ Miss
3. Check local cache
        ↓ Hit → Return
        ↓ Miss
4. Call real API
        ↓
5. Save to local cache
        ↓
6. Return result
```

## Output Examples

```
[Snapshot Hit] google_flights (task=T1-01, turn=1)
```

Or

```
[Cache Hit] google_flights
```

Or

```
[API Call] google_flights...
[Saved] google_flights -> /path/to/cache
```

## Cache File Structure

Cache is saved in the `nomad/src/cache/` directory:

```
cache/
├── google_flights_abc123def456.json
├── google_hotels_def456abc123.json
└── google_local_ghi789jkl012.json
```

Each filename contains:
- `engine` - Search engine type
- `cache_key` - MD5 hash based on parameters, ensures same parameters always hit the same cache

## API Parameters

### search_flights
- `origin` - Departure airport code (e.g., "BOS")
- `destination` - Arrival airport code (e.g., "SEA")
- `departure_date` - Departure date (YYYY-MM-DD)
- `return_date` - Return date (YYYY-MM-DD)
- `task_id` - Optional, for snapshot matching
- `turn` - Optional, turn number (default 1)

### search_hotels
- `location` - Location (e.g., "Seattle, Washington")
- `check_in` - Check-in date (YYYY-MM-DD)
- `check_out` - Check-out date (YYYY-MM-DD)
- `adults` - Number of adults (default 1)
- `task_id` - Optional, for snapshot matching
- `turn` - Optional, turn number (default 1)

### search_places
- `query` - Search query (e.g., "vegetarian restaurants")
- `location` - Location
- `task_id` - Optional, for snapshot matching
- `turn` - Optional, turn number (default 1)

## Configure .env

```env
SERP_API=your_serpapi_key_here
```

## Migration Guide

If you're already using the old `@cached_api_call` decorator version, no code changes needed! The new SerpManager is fully backward compatible:

```python
# Old code still works
from tools.serpapi import search_flights
result = search_flights(...)  # Auto-use new cache system
```
