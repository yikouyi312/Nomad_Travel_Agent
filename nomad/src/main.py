from src.agents.orchestrator import analyze_user_input, update_state_from_analysis
from src.agents.specialist import run_activities_specialist, run_logistics_specialist
from src.agents.verifier import verify_and_format_itinerary
from src.state import TravelState


def main():
    print("Welcome to Nomad Travel Agent!")
    print("Type 'quit' or 'exit' to stop.")
    print("-----------------------------------")

    state = TravelState()

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["quit", "exit"]:
            break

        # 1. Orchestrator: classify intent, extract constraints, decide delegation
        print("\n[Orchestrator] Analyzing input and updating Constraint Layer...")
        try:
            analysis = analyze_user_input(user_input, state)
            state = update_state_from_analysis(state, analysis)

            print(f"[Orchestrator] Intent: {analysis.get('intent')}")
            print(f"[Orchestrator] Delegation: {analysis.get('delegation')}")

            delegation = analysis.get("delegation", "none")

        except Exception as e:
            print(f"Error during orchestration: {e}")
            continue

        # 2. Add to message history
        state.messages.append({"role": "user", "content": user_input})

        # 3. Delegation
        if delegation == "none":
            response = analysis.get(
                "response_to_user",
                "I'm still missing some info to start planning.",
            )
            print(f"\nNomad: {response}")
            state.messages.append({"role": "assistant", "content": response})
            continue

        # If we reach here, we need to run specialists
        draft_components = []
        constraints_str = state.constraints.model_dump_json(indent=2)

        if delegation in ["logistics", "both"]:
            print("\n[Specialist - Logistics] Searching for flights & hotels...")
            try:
                logistics_draft = run_logistics_specialist(constraints_str)
                draft_components.append("--- LOGISTICS ---\n" + logistics_draft)
            except Exception as e:
                print(f"[Specialist Error] {e}")

        if delegation in ["activities", "both"]:
            print(
                "\n[Specialist - Activities] Searching for restaurants & things to do..."
            )
            try:
                activities_draft = run_activities_specialist(constraints_str)
                draft_components.append("--- ACTIVITIES ---\n" + activities_draft)
            except Exception as e:
                print(f"[Specialist Error] {e}")

        # 4. Verifier: check draft against constraints
        print("\n[Verifier] Checking itinerary against constraints...")
        full_draft = "\n\n".join(draft_components)

        try:
            verification = verify_and_format_itinerary(full_draft, constraints_str)

            if verification.get("is_valid"):
                final_response = verification.get(
                    "final_message_to_user", "Here is your plan!"
                )
                print("\nNomad:\n")
                print(final_response)
                state.messages.append({"role": "assistant", "content": final_response})
            else:
                issues = verification.get("issues", [])
                print(
                    f"\nNomad: I built a plan, but it violates some constraints:\n{issues}"
                )
                print("I will need to revise. Let me know how you'd like to adjust.")

        except Exception as e:
            print(f"Error during verification: {e}")


if __name__ == "__main__":
    main()
