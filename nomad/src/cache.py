import hashlib
import json
import os
from functools import wraps
from typing import Callable

from config import CACHE_DIR


def _generate_cache_key(func_name: str, *args, **kwargs) -> str:
    """Creates a deterministic hash based on function name and all arguments."""
    # Convert args and kwargs to a deterministic string
    cache_dict = {
        "func": func_name,
        "args": args,
        "kwargs": {k: v for k, v in sorted(kwargs.items())},
    }
    dict_str = json.dumps(cache_dict, sort_keys=True)
    return hashlib.md5(dict_str.encode("utf-8")).hexdigest()


def cached_api_call(func: Callable) -> Callable:
    """
    Decorator that caches the result of SerpAPI calls to JSON files.
    Ensures reproducibility for the benchmark and saves API credits.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = _generate_cache_key(func.__name__, *args, **kwargs)
        cache_file = os.path.join(CACHE_DIR, f"{func.__name__}_{cache_key}.json")

        # Return cached result if it exists
        if os.path.exists(cache_file):
            print(f"[CACHE HIT] {func.__name__}")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # Otherwise, execute the function
        print(f"[CACHE MISS] Calling real API for {func.__name__}")
        result = func(*args, **kwargs)

        # Cache the result
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    return wrapper
