from typing import Any, Dict, List, Optional

import requests
from config import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    CLAUDE_API_KEY,
    DEFAULT_MODEL,
    MAX_TOKENS,
)


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
) -> Dict[str, Any]:
    """
    Standard call for agent loops.
    Returns the raw response dictionary so the agent loop can process tool_use blocks.
    """
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
        "system": system,
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    resp = requests.post(
        ANTHROPIC_API_URL, headers=_get_headers(), json=payload, timeout=60
    )

    if resp.status_code != 200:
        raise Exception(
            f"Anthropic API call failed with status {resp.status_code}: {resp.text}"
        )

    return resp.json()


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

    # Extract the tool_use arguments
    for block in resp_data.get("content", []):
        if (
            block.get("type") == "tool_use"
            and block.get("name") == "output_structured_data"
        ):
            return block.get("input", {})

    raise Exception(f"Failed to extract structured data. Response was: {resp_data}")


def enhance_result_with_nlp(
    base_result: Dict[str, Any],
    additional_text: str,
    messages: List[Dict[str, Any]],
    schema: Dict[str, Any],
    system: str = "",
) -> Dict[str, Any]:
    """
    Calls LLM to process additional natural language text and merges the response
    with the base result. Only updates response_to_user field.
    
    Args:
        base_result: The base structured result (won't be modified for constraints)
        additional_text: Additional NLP query/text to process
        messages: Message history for context
        schema: Schema for structured output
        system: System prompt for LLM
    
    Returns:
        Updated result with merged response_to_user
    """
    try:
        messages_with_query = messages + [{"role": "user", "content": additional_text}]
        query_result = call_llm_structured(
            messages=messages_with_query, schema=schema, system=system
        )
        
        # Only merge the response_to_user field
        if query_result.get("response_to_user"):
            base_result["response_to_user"] += " " + query_result["response_to_user"]
        
        return base_result
    
    except Exception as e:
        print(f"[Warning] Failed to process additional query: {e}")
        return base_result


def extract_text(response: Dict[str, Any]) -> str:
    """Helper to extract text from a raw response"""
    text_blocks = [
        block["text"]
        for block in response.get("content", [])
        if block.get("type") == "text"
    ]
    return "\n".join(text_blocks)
