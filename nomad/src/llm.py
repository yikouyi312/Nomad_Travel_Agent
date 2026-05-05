from typing import Any, Dict, List, Optional

import hashlib
import json
import os
import time
import requests
from config import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    CLAUDE_API_KEY,
    DEFAULT_MODEL,
    LLM_CACHE_DIR,
    MAX_TOKENS,
)

# Retry config for rate limits
MAX_RETRIES = 5
INITIAL_BACKOFF = 30  # seconds — generous since limit is per-minute

# Task-scoped LLM cache: set via set_llm_task_id() so cache files land under task subfolder
_current_task_id: Optional[str] = None


def set_llm_task_id(task_id: Optional[str]) -> None:
    """Set the current task ID so LLM cache is saved under output/llm_cache/{task_id}/."""
    global _current_task_id
    _current_task_id = task_id


def _llm_cache_key(payload: Dict) -> str:
    """Generate a deterministic hash from the LLM request payload."""
    # Sort keys for determinism; exclude non-deterministic fields
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _llm_cache_dir() -> str:
    """Return task-scoped cache directory, or the global one if no task is set."""
    if _current_task_id:
        return os.path.join(LLM_CACHE_DIR, _current_task_id)
    return LLM_CACHE_DIR


def _load_llm_cache(key: str) -> Optional[Dict]:
    # Try task-scoped dir first, then fall back to global (for old cache files)
    for d in [_llm_cache_dir(), LLM_CACHE_DIR]:
        path = os.path.join(d, f"{key}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                print(f"  [LLM CACHE HIT] {key}")
                return json.load(f)
    return None


def _save_llm_cache(key: str, response: Dict) -> None:
    cache_dir = _llm_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    print(f"  [LLM CACHE SAVE] {key}")


def _get_headers() -> Dict[str, str]:
    return {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


def call_llm(
    messages: List[Dict[str, Any]],
    system: str = "",
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
    temperature: float = 0.0,
    model: str = DEFAULT_MODEL,
    use_cache: bool = True,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Standard call for agent loops.
    Returns the raw response dictionary so the agent loop can process tool_use blocks.
    Set use_cache=False to skip caching (e.g. for multi-turn ReAct loops).
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens or MAX_TOKENS,
        "temperature": temperature,
        "system": system,
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    # Check cache
    cache_key = None
    if use_cache:
        cache_key = _llm_cache_key(payload)
        cached = _load_llm_cache(cache_key)
        if cached is not None:
            return cached

    resp = requests.post(
        ANTHROPIC_API_URL, headers=_get_headers(), json=payload, timeout=120
    )

    if resp.status_code == 429:
        # Rate limited — retry with exponential backoff
        for attempt in range(1, MAX_RETRIES + 1):
            retry_after = int(resp.headers.get("retry-after", INITIAL_BACKOFF * attempt))
            print(f"  ⏳ Rate limited. Waiting {retry_after}s before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(retry_after)
            resp = requests.post(
                ANTHROPIC_API_URL, headers=_get_headers(), json=payload, timeout=120
            )
            if resp.status_code != 429:
                break

    if resp.status_code != 200:
        raise Exception(
            f"Anthropic API call failed with status {resp.status_code}: {resp.text}"
        )

    result = resp.json()

    # Save to cache
    if use_cache and cache_key:
        _save_llm_cache(cache_key, result)

    return result


def call_llm_structured(
    messages: List[Dict[str, Any]],
    schema: Dict[str, Any],
    system: str = "",
    temperature: float = 0.0,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    Uses the tool_choice = 'any' pattern to force Claude to output a specific JSON structure.
    Returns the parsed JSON dictionary.
    """

    # We create a dummy tool representing the structure we want it to output
    tools = [
        {
            "name": "output_structured_data",
            "description": "Output the final result matching this schema",
            "input_schema": schema,
        }
    ]

    tool_choice = {"type": "tool", "name": "output_structured_data"}

    resp_data = call_llm(
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        model=model,
    )

    # Detect truncation — if the model ran out of tokens the JSON is incomplete
    if resp_data.get("stop_reason") == "max_tokens":
        print("  [Warning] Structured output truncated (max_tokens). Retrying with higher limit...")
        resp_data = call_llm(
            messages=messages,
            system=system,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            model=model,
            use_cache=False,
            max_tokens=MAX_TOKENS * 2,
        )

    # Extract the tool_use arguments
    for block in resp_data.get("content", []):
        if (
            block.get("type") == "tool_use"
            and block.get("name") == "output_structured_data"
        ):
            return block.get("input", {})

    raise Exception(f"Failed to extract structured data. Response was: {resp_data}")


def extract_text(resp_data: Dict[str, Any]) -> str:
    """
    Extract all text content from an LLM response.
    
    Args:
        resp_data: Response dictionary from call_llm()
    
    Returns:
        Concatenated text from all text blocks in the response
    """
    text_parts = []
    for block in resp_data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return "".join(text_parts)
