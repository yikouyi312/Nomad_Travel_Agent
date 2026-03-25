from typing import Any, Dict

from llm import call_llm_structured

VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid": {
            "type": "boolean",
            "description": "True if the itinerary strictly obeys all constraints.",
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of constraint violations (e.g. 'Flight returns on 15th but constraint is 14th')",
        },
        "final_message_to_user": {
            "type": "string",
            "description": "A nicely formatted Markdown response presenting the final validated itinerary, or explaining what went wrong if it couldn't be built.",
        },
    },
    "required": ["is_valid", "issues", "final_message_to_user"],
}


def verify_and_format_itinerary(
    draft_text: str, constraints_json: str
) -> Dict[str, Any]:
    """
    Acts as the Verifier layer. Reviews the text output from the Specialists against
    the strict JSON Constraint layer.
    """

    system_prompt = """You are the Verifier for Nomad.
Your job is to cross-reference the proposed itinerary against the hard constraints.

HARD CONSTRAINTS:
{constraints_json}

If the itinerary violates any constraints (e.g. budget exceeded, dates wrong, wrong city),
set is_valid to false and list the issues.
If it is valid, format the draft into a beautiful Markdown response for the user."""

    messages = [
        {
            "role": "user",
            "content": f"Here is the draft itinerary to verify:\n\n{draft_text}",
        }
    ]

    result = call_llm_structured(
        messages=messages,
        schema=VERIFIER_SCHEMA,
        system=system_prompt.replace("{constraints_json}", constraints_json),
    )

    return result
