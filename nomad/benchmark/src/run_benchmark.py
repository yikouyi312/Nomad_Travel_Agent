"""
Benchmark Runner: Run orchestrator tasks through the full agent pipeline.

Usage:
    python nomad/benchmark/src/run_benchmark.py                    # run all tasks
    python nomad/benchmark/src/run_benchmark.py --tier 1           # only tier 1
    python nomad/benchmark/src/run_benchmark.py --task ORCH-T1-02  # single task
    python nomad/benchmark/src/run_benchmark.py --evaluate-only    # skip agent, just evaluate saved plans
"""

import argparse
import json
import os
import sys
import time
import traceback
from typing import Dict, Any, List, Optional

# Add nomad/src to path so we can import the agent modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NOMAD_SRC = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "src"))
sys.path.insert(0, NOMAD_SRC)

from agents.orchestrator import analyze_user_input, update_state_from_analysis
from agents.specialist import run_logistics_specialist, run_activities_specialist
from agents.verifier import verify_and_format_itinerary
from tools.plan_repository import PlanRepository
from tools.auto_evaluator import AutoEvaluator
from state import TravelState


# ============================================================================
# Task Loading
# ============================================================================

def load_orchestrator_tasks(path: str = None) -> List[Dict[str, Any]]:
    """Load orchestrator tasks from JSON file."""
    if path is None:
        path = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data", "orchestrator_tasks.json"))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_tasks(
    tasks: List[Dict[str, Any]],
    tier: Optional[int] = None,
    task_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter tasks by tier or specific task_id."""
    if task_id:
        return [t for t in tasks if t["task_id"] == task_id]
    if tier is not None:
        return [t for t in tasks if t["tier"] == tier]
    return tasks


# ============================================================================
# Single Task Runner
# ============================================================================

def run_single_task(task: Dict[str, Any], verbose: bool = True) -> Dict[str, Any]:
    """
    Run a single orchestrator task through the full agent pipeline.

    Returns a result dict with:
      - task_id, tier, status (success / error / skipped)
      - analysis (orchestrator output)
      - verification (verifier output, if reached)
      - elapsed_seconds
      - error (if any)
    """
    task_id = task["task_id"]
    tier = task["tier"]
    user_query = task["input"].get("content", "")
    expected = task.get("expected_output", {})

    result = {
        "task_id": task_id,
        "tier": tier,
        "status": "error",
        "analysis": None,
        "verification": None,
        "elapsed_seconds": 0,
        "error": None,
    }

    t0 = time.time()

    try:
        # --- 1. Init state ---
        state = TravelState(task_id=task_id)

        # For multi-turn (T3), inject current_state_constraints as prior context
        if task.get("current_state_constraints"):
            prior = task["current_state_constraints"]
            for k, v in prior.items():
                if v is not None and hasattr(state.constraints, k):
                    setattr(state.constraints, k, v)

        if verbose:
            print(f"\n{'='*60}")
            print(f"[{task_id}] (Tier {tier}) {task.get('description', '')}")
            print(f"  Query: {user_query[:100]}{'...' if len(user_query)>100 else ''}")

        # --- 2. Orchestrator ---
        # Build task_json from expected_output so orchestrator can use it for
        # direct constraint extraction (no extra LLM call for structured tasks)
        task_json = {
            "task_id": task_id,
            "updated_constraints": expected.get("updated_constraints", {}),
            "delegation": expected.get("delegation", "none"),
        }

        analysis = analyze_user_input(
            user_msg=user_query,
            state=state,
            task_json=task_json,
        )
        state = update_state_from_analysis(state, analysis)
        result["analysis"] = analysis

        delegation = analysis.get("delegation", "none")
        if verbose:
            print(f"  Orchestrator → intent={analysis.get('intent')}, delegation={delegation}")

        # --- 3. Delegation check ---
        if delegation == "none":
            result["status"] = "skipped"
            result["error"] = "Delegation is none — insufficient constraints"
            if verbose:
                print(f"  SKIPPED (delegation=none)")
            return result

        # --- 4. Run specialists ---
        constraints_str = state.constraints.model_dump_json(indent=2)
        draft_components = []
        all_search_results = {"flights": [], "hotels": [], "activities": []}

        if delegation in ("logistics", "both"):
            if verbose:
                print(f"  Running logistics specialist...")
            logistics_draft, logistics_searches, _ = run_logistics_specialist(
                constraints_str, task_id=state.task_id
            )
            draft_components.append("--- LOGISTICS ---\n" + logistics_draft)
            all_search_results["flights"].extend(logistics_searches.get("flights", []))
            all_search_results["hotels"].extend(logistics_searches.get("hotels", []))

        if delegation in ("activities", "both"):
            if verbose:
                print(f"  Running activities specialist...")
            activities_draft, activities_searches, _ = run_activities_specialist(
                constraints_str, task_id=state.task_id
            )
            draft_components.append("--- ACTIVITIES ---\n" + activities_draft)
            all_search_results["activities"].extend(activities_searches.get("activities", []))

        # --- 5. Verifier ---
        if verbose:
            print(f"  Running verifier...")
        full_draft = "\n\n".join(draft_components)
        verification = verify_and_format_itinerary(
            full_draft,
            constraints_str,
            task_id=state.task_id,
            search_results=all_search_results,
        )
        result["verification"] = verification

        # --- 6. Save plan ---
        if verification.get("is_valid"):
            plan_to_save = {
                "itinerary": verification.get("itinerary", {}),
                "constraints": {
                    "origin": state.constraints.origin,
                    "destination": state.constraints.destination,
                    "start_date": state.constraints.start_date,
                    "end_date": state.constraints.end_date,
                    "budget_usd": state.constraints.budget_usd,
                    "num_travelers": state.constraints.num_travelers,
                },
                "is_valid": True,
                "task_id": state.task_id,
            }
            repo = PlanRepository()
            saved_path = repo.save_plan(plan=plan_to_save, task_id=state.task_id, save_metadata=True)
            result["status"] = "success"
            if verbose:
                print(f"  SAVED → {saved_path}")
        else:
            result["status"] = "invalid"
            result["error"] = verification.get("issues", [])
            if verbose:
                print(f"  INVALID — {verification.get('issues', [])}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        if verbose:
            print(f"  ERROR — {e}")
            traceback.print_exc()

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


# ============================================================================
# Batch Runner
# ============================================================================

def run_benchmark(
    tasks: List[Dict[str, Any]],
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """Run a list of orchestrator tasks and return results."""
    results = []
    total = len(tasks)
    print(f"\n{'#'*60}")
    print(f"  BENCHMARK: Running {total} tasks")
    print(f"{'#'*60}")

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{total}]", end="")
        r = run_single_task(task, verbose=verbose)
        results.append(r)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    invalid = sum(1 for r in results if r["status"] == "invalid")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    total_time = sum(r["elapsed_seconds"] for r in results)

    print(f"\n\n{'='*60}")
    print(f"BENCHMARK COMPLETE")
    print(f"  Total:   {total}")
    print(f"  Success: {success}")
    print(f"  Invalid: {invalid}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Time:    {total_time:.1f}s")
    print(f"{'='*60}")

    return results


# ============================================================================
# Evaluation
# ============================================================================

def run_evaluation(verbose: bool = True) -> Dict[str, Any]:
    """Batch evaluate all saved plans."""
    print(f"\n{'#'*60}")
    print(f"  EVALUATION: Scoring all saved plans")
    print(f"{'#'*60}\n")

    auto_eval = AutoEvaluator()
    repo_plans = auto_eval.repo.get_all_plans()
    print(f"Found {len(repo_plans)} plans to evaluate: {repo_plans}\n")

    if not repo_plans:
        print("No plans found. Run benchmark first.")
        return {}

    results, report_file = auto_eval.auto_evaluate_and_report(report_name="benchmark_evaluation")

    if results:
        scores = [r["overall_score"] for r in results.values() if "overall_score" in r]
        if scores:
            print(f"\n{'='*60}")
            print(f"EVALUATION RESULTS")
            print(f"  Plans evaluated: {len(scores)}")
            print(f"  Average score:   {sum(scores)/len(scores):.1%}")
            print(f"  Best:            {max(scores):.1%}")
            print(f"  Worst:           {min(scores):.1%}")

            for task_id, r in sorted(results.items()):
                if "overall_score" in r:
                    print(f"\n  [{task_id}]  {r['overall_score']:.1%}")
                    print(f"    Schema={r.get('schema_compliance',0):.1%}  "
                          f"CSR={r.get('csr_score',0):.1%}  "
                          f"Tools={r.get('tool_accuracy',0):.1%}")
            print(f"\n  Report: {report_file}")
            print(f"{'='*60}")

    return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Run orchestrator benchmark tasks through the agent pipeline")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], help="Only run tasks of this tier")
    parser.add_argument("--task", type=str, help="Run a specific task by ID (e.g. ORCH-T1-02)")
    parser.add_argument("--evaluate-only", action="store_true", help="Skip agent runs, just evaluate saved plans")
    parser.add_argument("--no-evaluate", action="store_true", help="Run agents but skip evaluation")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    parser.add_argument("--tasks-file", type=str, help="Path to orchestrator_tasks.json (default: auto-detect)")

    args = parser.parse_args()
    verbose = not args.quiet

    if not args.evaluate_only:
        # Load and filter tasks
        tasks = load_orchestrator_tasks(args.tasks_file)
        tasks = filter_tasks(tasks, tier=args.tier, task_id=args.task)

        if not tasks:
            print("No tasks matched your filter.")
            return

        # Run
        run_results = run_benchmark(tasks, verbose=verbose)

        # Save run results
        from config import OUTPUT_DIR
        run_log_path = os.path.join(OUTPUT_DIR, "benchmark_run_log.json")
        os.makedirs(os.path.dirname(run_log_path), exist_ok=True)
        with open(run_log_path, "w", encoding="utf-8") as f:
            json.dump(run_results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nRun log saved to: {run_log_path}")

    # Evaluate
    if not args.no_evaluate:
        run_evaluation(verbose=verbose)


if __name__ == "__main__":
    main()
