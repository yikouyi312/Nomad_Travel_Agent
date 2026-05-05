from agents.orchestrator import analyze_user_input, update_state_from_analysis
from agents.specialist import (
    search_and_save_candidates,
    search_flight_candidates, search_hotel_candidates, search_activity_candidates,
    select_top_k,
    # Legacy imports for backward compatibility
    run_activities_specialist, run_logistics_specialist,
)
from agents.verifier import (
    validate_plan, format_negotiation_message,
    format_complete_itinerary, verify_and_format_itinerary,
)
from state import TravelState, TravelNeeds


def main():
    """
    New Pipeline:
      1. Orchestrator: parse query → extract constraints + detect needs (flight/hotel/activity)
      2. Search & Save: direct SerpAPI calls per needed category → save ALL raw data
      3. Select Top-K: programmatic filter → LLM picks best combination
      4. Validate & Negotiate: check constraints → if unmet, ask user accept or adjust → loop
    """
    print("Welcome to Nomad Travel Agent!")
    print("Commands: 'quit', 'save', 'load', 'sessions'")
    print("-----------------------------------")

    state = TravelState()

    while True:
        user_input = input("\nYou: ")
        cmd = user_input.strip().lower()
        if cmd in ["quit", "exit"]:
            break
        if cmd == "save":
            path = state.save_session()
            print(f"\nNomad: Session saved → {path}  (task_id: {state.task_id})")
            continue
        if cmd == "sessions":
            ids = TravelState.list_sessions()
            if ids:
                print("\nSaved sessions:")
                for sid in ids:
                    print(f"  • {sid}")
            else:
                print("\nNo saved sessions.")
            continue
        if cmd.startswith("load"):
            parts = cmd.split(None, 1)
            if len(parts) < 2:
                ids = TravelState.list_sessions()
                if not ids:
                    print("\nNo saved sessions.")
                    continue
                print("\nSaved sessions:")
                for i, sid in enumerate(ids, 1):
                    print(f"  {i}. {sid}")
                choice = input("Enter number or task_id: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(ids):
                    task_id = ids[int(choice) - 1]
                else:
                    task_id = choice
            else:
                task_id = parts[1]
            try:
                state = TravelState.load_session(task_id)
                print(f"\nNomad: Session restored (task_id: {state.task_id})")
                print(f"  Needs:  flight={state.needs.flight}, hotel={state.needs.hotel}, activity={state.needs.activity}")
                print(f"  Dest:   {state.constraints.destination or 'not set'}")
                print(f"  Dates:  {state.constraints.start_date} → {state.constraints.end_date}")
            except FileNotFoundError:
                print(f"\nSession '{task_id}' not found.")
            continue

        # ── Step 1: Orchestrator ─────────────────────────────────────
        print("\n[Orchestrator] Analyzing input...")
        try:
            analysis = analyze_user_input(user_input, state)
            state = update_state_from_analysis(state, analysis)

            print(f"  Intent: {analysis.get('intent')}")
            print(f"  Needs:  flight={state.needs.flight}, hotel={state.needs.hotel}, activity={state.needs.activity}")
        except Exception as e:
            print(f"Error during orchestration: {e}")
            continue

        state.messages.append({"role": "user", "content": user_input})

        # If no needs detected, just respond
        if not any([state.needs.flight, state.needs.hotel, state.needs.activity]):
            response = analysis.get(
                "response_to_user",
                "I'm still missing some info to start planning.",
            )
            print(f"\nNomad: {response}")
            state.messages.append({"role": "assistant", "content": response})
            continue

        # Check if we have enough info for each detected need independently
        missing = []
        if state.needs.flight and not state.constraints.is_ready_for_flight():
            if not state.constraints.origin: missing.append("departure city/airport")
            if not state.constraints.destination: missing.append("destination")
            if not state.constraints.start_date: missing.append("departure date")
            if not state.constraints.end_date: missing.append("return date")
        if state.needs.hotel and not state.constraints.is_ready_for_hotel():
            if not state.constraints.destination: missing.append("destination for hotel")
            if not state.constraints.start_date: missing.append("check-in date")
            if not state.constraints.end_date: missing.append("check-out date")
        if state.needs.activity and not state.constraints.destination:
            missing.append("destination for activities")
        
        if missing:
            response = analysis.get("response_to_user", "")
            if not response:
                response = f"I'd love to help! Could you provide: {', '.join(missing)}?"
            print(f"\nNomad: {response}")
            state.messages.append({"role": "assistant", "content": response})
            continue

        # Show orchestrator reply if any
        orchestrator_reply = analysis.get("response_to_user", "")
        if orchestrator_reply:
            print(f"\nNomad: {orchestrator_reply}")

        # ── Step 2: Search & Save All Candidates ────────────────────
        print("\n[Search] Fetching candidates...")
        constraints_str = state.constraints.model_dump_json(indent=2)
        
        try:
            search_results = search_and_save_candidates(
                constraints=state.constraints,
                needs=state.needs,
                task_id=state.task_id,
            )
            
            total = sum(len(v) for v in search_results.values())
            print(f"\n[Search] Done. {total} search calls completed.")
        except Exception as e:
            print(f"[Search Error] {e}")
            state.messages.append({"role": "assistant", "content": f"Error searching: {e}"})
            continue

        # ── Step 3: Top-K Selection with LLM ────────────────────────
        print("\n[Selector] Picking best combination...")
        try:
            selection = select_top_k(
                task_id=state.task_id,
                constraints_json=constraints_str,
                needs=state.needs,
                search_results=search_results,
                top_k=5,
            )
        except Exception as e:
            print(f"[Selector Error] {e}")
            state.messages.append({"role": "assistant", "content": f"Error selecting plan: {e}"})
            continue

        # ── Step 4: Validate & Negotiate ────────────────────────────
        print("\n[Validator] Checking constraints...")
        validation = validate_plan(selection, state.constraints)

        if validation["valid"]:
            # All constraints met — show the plan
            formatted = format_complete_itinerary({
                "is_valid": True,
                "issues": [],
                "itinerary": validation["plan"],
                "final_message_to_user": selection.get("final_message_to_user", "Here is your plan!"),
            })
            print("\n" + formatted)
            state.last_verification = selection
            state.messages.append({"role": "assistant", "content": formatted})
            state.save_session()  # Auto-save after successful plan
        else:
            # Constraints not met — negotiate
            negotiation_msg = format_negotiation_message(validation)
            print("\n" + negotiation_msg)
            state.messages.append({"role": "assistant", "content": negotiation_msg})
            
            # Wait for user response
            user_response = input("\nYou: ").strip().lower()
            state.messages.append({"role": "user", "content": user_response})
            
            if user_response in ("accept", "yes", "ok", "sure", "fine"):
                # Use closest alternative or the original plan
                plan_to_show = validation.get("closest_alternative") or validation["plan"]
                formatted = format_complete_itinerary({
                    "is_valid": False,
                    "issues": validation["unmet_constraints"],
                    "itinerary": plan_to_show,
                    "final_message_to_user": "Here is the closest feasible plan.",
                })
                print("\n" + formatted)
                state.last_verification = {"itinerary": plan_to_show}
                state.messages.append({"role": "assistant", "content": formatted})
            else:
                # User wants to adjust — feed back through orchestrator
                print("\nNomad: Got it, let me re-process with your updated constraints...")
                # The next loop iteration will pick up this message
                # and the orchestrator will update constraints


if __name__ == "__main__":
    main()
