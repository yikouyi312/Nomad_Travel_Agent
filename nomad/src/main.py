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
        orchestrator_reply = analysis.get("response_to_user", "")
        if orchestrator_reply:
            print(f"\nNomad: {orchestrator_reply}")
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
                # 把验证结果存入 state，供后续多轮对话使用
                state.last_verification = verification
                state.messages.append({"role": "assistant", "content": complete_itinerary_str})
            else:
                issues = verification.get("issues", [])
                issues_str = "\n".join(f"- {i}" for i in issues)
                print(f"\n[Verifier] Found issues, attempting recovery...\n{issues_str}")

                # 把 issues 反馈给 orchestrator，触发重新委派
                recovery_msg = f"The previous plan had these issues:\n{issues_str}\nPlease fix them."
                try:
                    recovery_analysis = analyze_user_input(recovery_msg, state)
                    state = update_state_from_analysis(state, recovery_analysis)
                    recovery_delegation = recovery_analysis.get("delegation", "none")

                    if recovery_delegation != "none":
                        print("\n[Recovery] Re-running specialists...")
                        # 重新跑 specialist，逻辑与上面一致
                        recovery_drafts = []
                        recovery_searches = {"flights": [], "hotels": [], "activities": []}

                        if recovery_delegation in ["logistics", "both"]:
                            r_draft, r_search, _ = run_logistics_specialist(
                                state.constraints.model_dump_json(indent=2),
                                task_id=state.task_id
                            )
                            recovery_drafts.append("--- LOGISTICS ---\n" + r_draft)
                            recovery_searches["flights"].extend(r_search.get("flights", []))
                            recovery_searches["hotels"].extend(r_search.get("hotels", []))

                        if recovery_delegation in ["activities", "both"]:
                            r_draft, r_search, _ = run_activities_specialist(
                                state.constraints.model_dump_json(indent=2),
                                task_id=state.task_id
                            )
                            recovery_drafts.append("--- ACTIVITIES ---\n" + r_draft)
                            recovery_searches["activities"].extend(r_search.get("activities", []))

                        recovery_verification = verify_and_format_itinerary(
                            "\n\n".join(recovery_drafts),
                            state.constraints.model_dump_json(indent=2),
                            task_id=state.task_id,
                            search_results=recovery_searches,
                        )

                        if recovery_verification.get("is_valid"):
                            complete_itinerary_str = format_complete_itinerary(recovery_verification)
                            print("\n[Recovery] ✅ Fixed!\n" + complete_itinerary_str)
                            state.messages.append({"role": "assistant", "content": complete_itinerary_str})
                        else:
                            remaining = recovery_verification.get("issues", [])
                            msg = f"I tried to fix the plan but still have issues: {remaining}\nPlease clarify your constraints."
                            print(f"\nNomad: {msg}")
                            state.messages.append({"role": "assistant", "content": msg})
                    else:
                        msg = f"I found issues but couldn't determine how to fix them automatically:\n{issues_str}"
                        print(f"\nNomad: {msg}")
                        state.messages.append({"role": "assistant", "content": msg})

                except Exception as e:
                    print(f"[Recovery Error] {e}")
        except Exception as e:
            print(f"Error during verification: {e}")


if __name__ == "__main__":
    main()
