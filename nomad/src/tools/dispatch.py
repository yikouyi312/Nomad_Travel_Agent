import json
from typing import Any, Dict, Optional

from tools.serpapi import SerpManager, search_flights, search_hotels, search_places
from tools.serpapi import _get_default_manager

# Global SerpManager instance
_serp_manager: Optional[SerpManager] = None


def get_serp_manager(
    api_key: Optional[str] = None, snapshot_path: Optional[str] = None
) -> SerpManager:
    return _get_default_manager()


TOOL_REGISTRY = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "search_places": search_places,
}


def dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a tool from the registry with the provided arguments.
    Returns the result formatted as a dictionary.
    
    Now supports optional task_id and turn parameters for calling SerpManager.
    """
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        print(f"  🔧 Executing tool {tool_name} with arguments {arguments}")
        
        # Get task_id and turn (if provided)
        task_id = arguments.pop("task_id", None)
        turn = arguments.pop("turn", 1)
        
        # For specific tools, use SerpManager and pass task_id and turn
        if tool_name == "search_flights":
            manager = get_serp_manager()
            result, candidate_count = manager.search_flights(task_id=task_id, turn=turn, **arguments)
            print(f"✈️  Flights results: {len(result.get('best_flights', []))} options")
        elif tool_name == "search_hotels":
            manager = get_serp_manager()
            result, candidate_count = manager.search_hotels(task_id=task_id, turn=turn, **arguments)
            print(f"🏨  Hotels results: {len(result.get('properties', []))} options")
        elif tool_name == "search_places":
            manager = get_serp_manager()
            result, candidate_count = manager.search_places(task_id=task_id, turn=turn, **arguments)
            print(f"🍽️  Places results: {len(result.get('local_results', []))} options")
        else:
            candidate_count = 0
        
        return result, candidate_count
    except Exception as e:
        print(f"  ❌ Tool {tool_name} error: {str(e)}")
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
        "content": json.dumps(result, indent=2, ensure_ascii=False),
    }
