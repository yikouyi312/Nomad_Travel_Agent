import json
import os

from anthropic import Anthropic


class DirectBaseline:
    """
    Direct-Prompting Baseline Agent (No Tools).
    Used as a control group to measure the impact of real-time search
    vs. LLM hallucination/internal knowledge.
    """

    def __init__(self, api_key, model_name="claude-sonnet-4-5-20250929"):
        self.client = Anthropic(api_key=api_key)
        self.model = model_name

    def solve(self, task_context):
        """
        Directly generates an itinerary based on the prompt.
        Matches the output format of the SerpAgent for fair comparison.
        """
        prompt = task_context["query"]
        history = task_context.get("history", [])

        # --- 1. CONSISTENT SYSTEM PROMPT ---
        # We keep the formatting rules identical to the SerpAgent
        system_prompt = (
            "You are a robotic Travel Planner. \n"
            "STRICT OUTPUT RULES:\n"
            "1. START directly with a Markdown table of the itinerary.\n"
            "2. NO conversational filler (e.g., 'Sure', 'I will plan...').\n"
            "3. MANDATORY SECTION: 'Budget Audit' at the end. \n"
            "   - List all estimated costs based on your internal knowledge.\n"
            "   - Calculate the FINAL TOTAL and compare it with the user budget.\n"
            f"USER CONSTRAINTS: {json.dumps(task_context.get('constraints', {}))}\n"
            f"USER PREFERENCES: {json.dumps(task_context.get('preferences', {}))}"
        )

        # --- 2. MESSAGE HISTORY (Tier 3 Support) ---
        messages = []
        for turn in history:
            messages.append({"role": "user", "content": turn})
            messages.append(
                {
                    "role": "assistant",
                    "content": "Acknowledged. Updating the static plan.",
                }
            )
        messages.append({"role": "user", "content": prompt})

        # --- 3. DIRECT INFERENCE (No Tool Call Loop) ---
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            temperature=0,  # Zero temperature for benchmark consistency
        )

        # Returns the text and an empty log (since no tools were used)
        itinerary = response.content[0].text
        return itinerary, []


class SerpAgent:
    """
    Nomad Travel Agent with Real-time Search and Automated Budgeting.
    Features:
    - ReAct pattern (Reasoning + Action)
    - Auto-Budget Calculation
    - Strict Markdown Output
    """

    def __init__(self, api_key, tool_provider, model_name="claude-sonnet-4-5-20250929"):
        self.client = Anthropic(api_key=api_key)
        self.tool_provider = tool_provider  # Instance of SerpManager
        self.model = model_name

    def _get_tools_schema(self):
        """Standard tool definitions for SerpAPI travel search."""
        return [
            {
                "name": "search_travel_data",
                "description": "Fetch real-time flight or hotel information from Google.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "enum": ["google_flights", "google_hotels", "google_maps"],
                        },
                        "params": {
                            "type": "object",
                            "description": "API specific parameters like departure_id, arrival_id, or check_in_date.",
                        },
                    },
                    "required": ["engine", "params"],
                },
            }
        ]

    def solve(self, task_context):
        """
        Complete logic to solve a travel task:
        1. Context Loading & History Management
        2. Tool Call (Action Layer)
        3. Data Synthesis & Budget Calculation (Synthesis Layer)
        """

        # --- 1. SYSTEM PROMPT: Constraint Injection & Output Formatting ---
        # We force the model to calculate totals and use a table format.
        system_prompt = (
            "You are a robotic Travel Planner. \n"
            "STRICT OUTPUT RULES:\n"
            "1. START directly with a Markdown table of the itinerary.\n"
            "2. NO conversational filler (e.g., 'Sure', 'I found these...').\n"
            "3. MANDATORY SECTION: 'Budget Audit' at the end. \n"
            "   - List all costs extracted from tool results.\n"
            "   - Calculate the FINAL TOTAL and compare it with the user budget.\n"
            f"USER CONSTRAINTS: {json.dumps(task_context.get('constraints', {}))}\n"
            f"USER PREFERENCES: {json.dumps(task_context.get('preferences', {}))}"
        )

        # --- 2. MESSAGE HISTORY MANAGEMENT (Tier 3 Support) ---
        messages = []
        for turn in task_context.get("history", []):
            messages.append({"role": "user", "content": turn})
            messages.append(
                {"role": "assistant", "content": "Acknowledged. Requirement updated."}
            )
        messages.append({"role": "user", "content": task_context["query"]})

        # --- 3. STEP 1: INITIAL INFERENCE (Requesting Tool Use) ---
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            tools=self._get_tools_schema(),
            messages=messages,
        )

        logs = []
        # Safely find the tool_use block
        tool_use_block = next(
            (block for block in response.content if block.type == "tool_use"), None
        )

        if tool_use_block:
            # --- 4. STEP 2: ACTION (Executing the search) ---
            engine = tool_use_block.input.get("engine")
            params = tool_use_block.input.get("params")
            task_id = task_context["task_id"]
            turn = len(task_context.get("history", [])) + 1

            # Fetch data by task_id + turn — reproducible regardless of agent params
            observation = self.tool_provider.fetch(
                engine, params, task_id=task_id, turn=turn, mode="mock"
            )
            logs.append({"tool": engine, "params": params})

            # --- 5. STEP 3: SYNTHESIS (Generating the final calculated plan) ---
            final_response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages
                + [
                    {
                        "role": "assistant",
                        "content": response.content,
                    },  # Original thought + tool_use
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_block.id,
                                "content": json.dumps(observation),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": "Now, generate the final itinerary table and the 'Budget Audit' based on these real results.",
                    },
                ],
            )
            return final_response.content[0].text, logs

        # Fallback if the agent decides not to use tools
        text_output = "".join([b.text for b in response.content if b.type == "text"])
        return text_output, logs
