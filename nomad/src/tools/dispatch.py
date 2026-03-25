import json
from typing import Any, Dict

from tools.serpapi import search_flights, search_hotels, search_places

TOOL_REGISTRY = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "search_places": search_places,
}


def dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a tool from the registry with the provided arguments.
    Returns the result formatted as a dictionary.
    """
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        func = TOOL_REGISTRY[tool_name]
        print(f"  🔧 Executing tool {tool_name} with {arguments}")
        result = func(**arguments)
        return result
    except Exception as e:
        print(f"  ❌ Error in tool {tool_name}: {str(e)}")
        return {"error": str(e)}


def create_tool_result_message(
    tool_use_id: str, tool_name: str, result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Formats the tool execution result into an Anthropic tool_result message.
    """
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result, indent=2),
    }
