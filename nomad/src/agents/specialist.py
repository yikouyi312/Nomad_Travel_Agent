from typing import Any, Dict, List

from config import MAX_AGENT_TURNS
from llm import call_llm, extract_text
from tools.dispatch import create_tool_result_message, dispatch_tool
from tools.schemas import ACTIVITIES_TOOLS, LOGISTICS_TOOLS


def run_specialist(
    task_description: str, tools: List[Dict[str, Any]], constraints_json: str
) -> str:
    """
    The canonical ReAct tool-calling loop.
    Executes tools until it reaches a final answer or max turns.
    """

    system_prompt = f"""You are a specialized Nomad Sub-Agent.
Your task: {task_description}

You must adhere strictly to these constraints:
{constraints_json}

Use your tools to find REAL data that matches the constraints. 
If no exact match is found, relax soft constraints but NEVER violate dates or budget.
Return a final, detailed summary of your findings."""

    messages = [
        {
            "role": "user",
            "content": "Please begin your search and provide the best options.",
        }
    ]

    turn = 0
    while turn < MAX_AGENT_TURNS:
        print(f"  [Specialist Turn {turn + 1}] Thinking...")

        response = call_llm(messages=messages, system=system_prompt, tools=tools)

        stop_reason = response.get("stop_reason")
        content_blocks = response.get("content", [])

        # Append assistant response (which might contain tool_uses and text)
        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason != "tool_use":
            # We are done!
            return extract_text(response)

        # We need to execute tools
        tool_results = []
        for block in content_blocks:
            if block["type"] == "tool_use":
                tool_use_id = block["id"]
                tool_name = block["name"]
                tool_args = block["input"]

                result = dispatch_tool(tool_name, tool_args)
                tool_results.append(
                    create_tool_result_message(tool_use_id, tool_name, result)
                )

        # Append tool results as a user message
        messages.append({"role": "user", "content": tool_results})

        turn += 1

    return "Error: Specialist reached maximum tool turns without a final answer."


def run_logistics_specialist(constraints_json: str) -> str:
    """Specialist for finding flights and hotels."""
    return run_specialist(
        task_description="Find the best flights and hotels for the trip.",
        tools=LOGISTICS_TOOLS,
        constraints_json=constraints_json,
    )


def run_activities_specialist(constraints_json: str) -> str:
    """Specialist for finding restaurants and things to do."""
    return run_specialist(
        task_description="Find restaurants (matching dietary needs) and activities (matching interests).",
        tools=ACTIVITIES_TOOLS,
        constraints_json=constraints_json,
    )
