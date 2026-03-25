from src.agents.orchestrator import analyze_user_input, update_state_from_analysis
from src.agents.specialist import run_activities_specialist, run_logistics_specialist
from src.agents.verifier import verify_and_format_itinerary, format_complete_itinerary
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
        all_search_results = {
            "flights": [],
            "hotels": [],
            "activities": [],
        }
        specialist_contexts = {
            "logistics": None,
            "activities": None,
        }
        constraints_str = state.constraints.model_dump_json(indent=2)

        if delegation in ["logistics", "both"]:
            print("\n[Specialist - Logistics] Searching for flights & hotels...")
            try:
                logistics_draft, logistics_searches, logistics_context = run_logistics_specialist(
                    constraints_str, 
                    task_id=state.task_id
                )
                draft_components.append("--- LOGISTICS ---\n" + logistics_draft)
                
                # Accumulate search results  
                all_search_results["flights"].extend(logistics_searches.get("flights", []))
                all_search_results["hotels"].extend(logistics_searches.get("hotels", []))
                
                # Store specialist context
                specialist_contexts["logistics"] = logistics_context
            except Exception as e:
                print(f"[Specialist Error] {e}")

        if delegation in ["activities", "both"]:
            print(
                "\n[Specialist - Activities] Searching for restaurants & things to do..."
            )
            try:
                activities_draft, activities_searches, activities_context = run_activities_specialist(
                    constraints_str,
                    task_id=state.task_id
                )
                draft_components.append("--- ACTIVITIES ---\n" + activities_draft)
                
                # Accumulate search results
                all_search_results["activities"].extend(activities_searches.get("activities", []))
                
                # Store specialist context
                specialist_contexts["activities"] = activities_context
            except Exception as e:
                print(f"[Specialist Error] {e}")

        # 4. Verifier: check draft against constraints
        print("\n[Verifier] Checking itinerary against constraints...")
        full_draft = "\n\n".join(draft_components)

        try:
            verification = verify_and_format_itinerary(
                full_draft, 
                constraints_str,
                task_id=state.task_id,
                search_results=all_search_results,  # <-- Pass accumulated search results
            )

            if verification.get("is_valid"):
                # Display complete itinerary
                complete_itinerary_str = format_complete_itinerary(verification)
                print("\n" + complete_itinerary_str)
                
                state.messages.append({"role": "assistant", "content": complete_itinerary_str})
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
