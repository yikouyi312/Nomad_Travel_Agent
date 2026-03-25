import hashlib
import json
import os
from typing import Any, Dict, Optional

import requests
from config import SERP_API_KEY

SERP_API_URL = "https://serpapi.com/search"

from config import CACHE_DIR


class SerpManager:
    """
    Unified SerpAPI manager supporting:
    1. Automatic cache checking (return if exists, call API if not)
    2. Automatic saving to local cache
    3. Support for multiple API engines (flights, hotels, places)
    4. Optional snapshot mode (for benchmark reproducibility)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = CACHE_DIR,
        snapshot_path: Optional[str] = None,
    ):
        """
        Args:
            api_key: SerpAPI key (if empty, only use cache and snapshot)
            cache_dir: Local cache directory
            snapshot_path: Snapshot file path (for benchmark, highest priority)
        """
        self.api_key = api_key or SERP_API_KEY
        self.cache_dir = cache_dir
        self.snapshot_path = snapshot_path
        os.makedirs(self.cache_dir, exist_ok=True)

        # Load snapshot and cache
        self.snapshot = self._load_snapshot() if snapshot_path else {}
        self.cache = {}  # In-memory cache for current session
        self._call_counters = {}  # Call counter for snapshot

    def _load_snapshot(self) -> Dict[str, Any]:
        """Load snapshot file (for benchmark)"""
        if not self.snapshot_path or not os.path.exists(self.snapshot_path):
            return {}
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"⚠️ Failed to load snapshot file: {self.snapshot_path}")
            return {}

    def _generate_cache_key(self, engine: str, **params) -> str:
        """Generate deterministic cache key"""
        cache_dict = {
            "engine": engine,
            "params": {k: v for k, v in sorted(params.items())},
        }
        dict_str = json.dumps(cache_dict, sort_keys=True)
        return hashlib.md5(dict_str.encode("utf-8")).hexdigest()

    def _get_cache_filename(self, engine: str, cache_key: str) -> str:
        """Get cache filename"""
        return f"{engine}_{cache_key}.json"

    def _check_snapshot(
        self,
        task_id: Optional[str],
        turn: int,
        engine: str,
        cache_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check snapshot with intelligent query type detection.
        Supports separate cache tracking for flights, hotels, and activities.
        
        Args:
            task_id: Task identifier (required for snapshot lookup)
            turn: Turn number
            engine: Engine type (google_flights, google_hotels, google_local)
            cache_key: Optional MD5 hash key for parameter-based lookup
        
        Returns:
            Cached result or None if not found
        """
        if not task_id or not self.snapshot:
            return None

        # Determine query type from engine
        query_type = {
            "google_flights": "flights",
            "google_hotels": "hotels",
            "google_local": "activities",
        }.get(engine, engine)

        turn_key = f"turn_{turn}"
        
        # Try lookup with cache_key first (most specific)
        if cache_key:
            results = (
                self.snapshot.get(task_id, {})
                .get(turn_key, {})
                .get(query_type, {})
                .get(cache_key, [])
            )
            
            if results:
                counter_key = (task_id, turn_key, query_type, cache_key)
                idx = self._call_counters.get(counter_key, 0)
                if idx < len(results):
                    self._call_counters[counter_key] = idx + 1
                    return results[idx]
        
        # Fallback to engine-level lookup (for backward compatibility)
        results = (
            self.snapshot.get(task_id, {})
            .get(turn_key, {})
            .get(query_type, [])
        )

        if results and isinstance(results, list):
            counter_key = (task_id, turn_key, query_type)
            idx = self._call_counters.get(counter_key, 0)
            if idx < len(results):
                self._call_counters[counter_key] = idx + 1
                return results[idx]

        return None

    def _check_local_cache(self, engine, cache_key):
        filename = self._get_cache_filename(engine, cache_key)
        
        # 先查本次运行的内存缓存（避免重复读文件）
        if filename in self.cache:
            return self.cache[filename]
        
        # 再查文件（只读这一个文件，不是全部）
        filepath = os.path.join(self.cache_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.cache[filename] = data      # 存入内存，下次直接用
                return data
        
        return None

    def _save_to_cache(
        self, engine: str, cache_key: str, data: Dict[str, Any]
    ) -> None:
        """Save to local cache"""
        filename = self._get_cache_filename(engine, cache_key)
        filepath = os.path.join(self.cache_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.cache[filename] = data

    def _call_api(self, engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call real SerpAPI"""
        api_params = {
            "engine": engine,
            "api_key": self.api_key,
            **params,
        }

        response = requests.get(SERP_API_URL, params=api_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search(
        self,
        engine: str,
        task_id: Optional[str] = None,
        turn: int = 1,
        **params,
    ) -> Dict[str, Any]:
        """
        Unified search interface (cache priority)

        Args:
            engine: "google_flights", "google_hotels", "google_local"
            task_id: Optional, for snapshot query
            turn: Turn number (default 1)
            **params: API parameters

        Returns:
            API result
        """
        # Generate cache key for parameter-based lookups
        cache_key = self._generate_cache_key(engine, **params)
        
        # 1. Check snapshot first (benchmark reproducibility)
        # Now supports separate cache for flights/hotels/activities
        if task_id:
            snapshot_result = self._check_snapshot(task_id, turn, engine, cache_key)
            if snapshot_result:
                print(f"[Snapshot Hit] {engine} (task={task_id}, turn={turn})")
                return snapshot_result

        # 2. Check local cache
        cached_result = self._check_local_cache(engine, cache_key)
        if cached_result:
            print(f"[Cache Hit] {engine}")
            return cached_result

        # 3. Call real API
        print(f"[API Call] {engine}...")
        result = self._call_api(engine, params)

        # 4. Save to cache
        self._save_to_cache(engine, cache_key, result)
        print(f"[Saved] {engine} -> {self.cache_dir}")

        return result

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        task_id: Optional[str] = None,
        turn: int = 1,
        topk_limit: int = 3
    ) -> Dict[str, Any]:
        """Search flights"""
        params = {
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "return_date": return_date,
            "currency": "USD",
            "hl": "en",
        }

        result = self.search(
            engine="google_flights",
            task_id=task_id,
            turn=turn,
            **params,
        )

        # Keep only top results to reduce token usage
        best_flights = result.get("best_flights", [])[:topk_limit]
        other_flights = result.get("other_flights", [])[:topk_limit]

        return {"best_flights": best_flights, "other_flights": other_flights}, len(best_flights) + len(other_flights)

    def search_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        adults: int = 1,
        task_id: Optional[str] = None,
        turn: int = 1,
        topk_limit: int = 5
    ) -> Dict[str, Any]:
        """Search hotels"""
        params = {
            "q": location,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adults,
            "currency": "USD",
            "hl": "en",
        }

        result = self.search(
            engine="google_hotels",
            task_id=task_id,
            turn=turn,
            **params,
        )

        # Keep only top results
        properties = result.get("properties", [])[:topk_limit]

        return {"properties": properties}, len(properties)

    def search_places(
        self,
        query: str,
        location: str,
        task_id: Optional[str] = None,
        turn: int = 1,
        topk_limit: int = 5
    ) -> Dict[str, Any]:
        """Search places/restaurants/attractions"""
        params = {
            "q": query,
            "location": location,
            "hl": "en",
            "gl": "us",
        }

        result = self.search(
            engine="google_local",
            task_id=task_id,
            turn=turn,
            **params,
        )

        # Keep only top results
        results = result.get("local_results", [])[:topk_limit]

        return {"local_results": results}, len(results)


# ============================================================================
# Backward compatibility: preserve old function interfaces
# ============================================================================


_default_manager = None


def _get_default_manager() -> SerpManager:
    """Get default SerpManager instance"""
    global _default_manager
    if _default_manager is None:
        _default_manager = SerpManager(api_key=SERP_API_KEY)
    return _default_manager


def search_flights(
    origin: str, destination: str, departure_date: str, return_date: str
) -> Dict[str, Any]:
    """
    Search flights (backward compatible interface)
    """
    manager = _get_default_manager()
    return manager.search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
    )


def search_hotels(
    location: str, check_in: str, check_out: str, adults: int = 1
) -> Dict[str, Any]:
    """
    Search hotels (backward compatible interface)
    """
    manager = _get_default_manager()
    return manager.search_hotels(
        location=location,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
    )


def search_places(query: str, location: str) -> Dict[str, Any]:
    """
    Search places (backward compatible interface)
    """
    manager = _get_default_manager()
    return manager.search_places(query=query, location=location)
