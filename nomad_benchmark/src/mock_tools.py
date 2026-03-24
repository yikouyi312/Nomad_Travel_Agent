import json
import os

from serpapi import GoogleSearch


class SerpManager:
    """
    Manages travel data retrieval using SerpAPI with a local caching mechanism
    to ensure benchmark reproducibility and cost efficiency.

    Snapshot structure:
        {
            "T1-01": {
                "turn_1": {
                    "google_flights": [ {result}, ... ]
                }
            },
            "T3-02": {
                "turn_1": {
                    "google_flights": [ {result} ],
                    "google_hotels":  [ {result} ]
                },
                "turn_2": {
                    "google_hotels": [ {result} ],
                    "google_maps":   [ {result} ]
                }
            }
        }

    - Tier 1 & 2 (single-turn): always "turn_1"
    - Tier 3 (multi-turn): each turn has its own engine results, reflecting
      what the agent searches for at that point in the conversation
    - Multiple calls to the same engine within a turn are stored as an ordered
      list and served sequentially via a call counter.
    """

    def __init__(self, api_key=None, cache_path="data/serp_snapshot.json"):
        self.api_key = api_key
        self.cache_path = cache_path
        self.cache = self._load_cache()
        self._call_counters = {}  # (task_id, turn_key, engine) -> call index

    def _load_cache(self):
        """Loads the local JSON cache with error handling for empty files."""
        if os.path.exists(self.cache_path):
            try:
                if os.path.getsize(self.cache_path) == 0:
                    return {}
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(
                    f"⚠️ Warning: {self.cache_path} is corrupted. Initializing new cache."
                )
                return {}
        return {}

    def reset_task(self, task_id):
        """Reset call counters for a task. Call at the start of each evaluation run."""
        for key in list(self._call_counters):
            if key[0] == task_id:
                del self._call_counters[key]

    def fetch(self, engine, params, task_id, turn=1, mode="auto"):
        """
        Fetch travel data for a specific task, turn, and engine.

        Args:
            engine:   "google_flights", "google_hotels", or "google_maps"
            params:   API parameters (used only for live API calls)
            task_id:  Benchmark task ID (e.g. "T1-01", "T3-02")
            turn:     Conversation turn number (1 for Tier 1/2; 1 or 2 for Tier 3)
            mode:     "mock"   — snapshot only; raises on miss
                      "auto"   — snapshot first, live API on miss
                      "record" — always calls live API and overwrites snapshot
        """
        turn_key = f"turn_{turn}"
        key = (task_id, turn_key, engine)
        idx = self._call_counters.get(key, 0)

        # 1. Try snapshot (mock / auto)
        if mode in ["mock", "auto"]:
            results = self.cache.get(task_id, {}).get(turn_key, {}).get(engine, [])
            if idx < len(results):
                self._call_counters[key] = idx + 1
                return results[idx]

        # 2. Snapshot miss in mock mode — cannot proceed
        if mode == "mock":
            raise Exception(
                f"Cache Miss: No snapshot for {task_id}/{turn_key}/{engine}[{idx}]. "
                f"Run seed_snapshots.py to populate the snapshot."
            )

        # 3. Live API call (auto miss or record mode)
        print(f"📡 Calling SerpAPI: {task_id}/{turn_key}/{engine}[{idx}]...")
        if not self.api_key:
            raise ValueError("API Key is required for live API calls.")

        search_params = {**params, "engine": engine, "api_key": self.api_key}
        result = GoogleSearch(search_params).get_dict()

        # 4. Save into task/turn/engine structure
        self.cache.setdefault(task_id, {}).setdefault(turn_key, {}).setdefault(
            engine, []
        )
        target = self.cache[task_id][turn_key][engine]
        if idx < len(target):
            target[idx] = result  # overwrite (record mode)
        else:
            target.append(result)

        self._call_counters[key] = idx + 1
        self._save_cache()
        print(f"✅ Saved: {task_id}/{turn_key}/{engine}[{idx}]")
        return result

    def _save_cache(self):
        """Persists the current cache to disk."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4, ensure_ascii=False)
