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
from agents.specialist import (
    search_flight_candidates, search_hotel_candidates, search_activity_candidates,
    select_top_k,
)
from agents.verifier import validate_plan, format_complete_itinerary
from tools.plan_repository import PlanRepository
from tools.auto_evaluator import AutoEvaluator
from state import TravelState
from llm import set_llm_task_id
from statistics import bootstrap_ci, cohens_d


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
    """Filter tasks by tier or specific task_id (prefix match)."""
    if task_id:
        return [t for t in tasks if t["task_id"] == task_id or t["task_id"].startswith(task_id + "-")]
    if tier is not None:
        return [t for t in tasks if t["tier"] == tier]
    return tasks


# ============================================================================
# Single Task Runner
# ============================================================================

def run_single_task(task: Dict[str, Any], verbose: bool = True, prior_state: Optional["TravelState"] = None) -> Dict[str, Any]:
    """
    Run a single orchestrator task through the new pipeline:
      Orchestrator (needs) → Search independently → Top-K selection → Validate

    Args:
        task: Task definition dict
        verbose: Print progress
        prior_state: If provided, use this as the starting state instead of
                     creating a fresh one. Used by run_multi_turn_task() to
                     chain turns dynamically.

    Returns a result dict with:
      - task_id, tier, status (success / error / skipped)
      - analysis (orchestrator output)
      - selection (top-K LLM output)
      - validation (constraint check)
      - elapsed_seconds
      - error (if any)
      - final_state: the TravelState after this turn (for chaining)
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
        "selection": None,
        "validation": None,
        "elapsed_seconds": 0,
        "error": None,
        "final_state": None,
    }

    t0 = time.time()

    try:
        # --- 1. Init state ---
        if prior_state is not None:
            # Multi-turn: continue from previous turn's state
            state = prior_state
            state.task_id = task_id
        else:
            state = TravelState(task_id=task_id)

            # For multi-turn (T3) without prior_state, fall back to hardcoded injection
            if task.get("current_state_constraints"):
                prior = task["current_state_constraints"]
                for k, v in prior.items():
                    if v is not None and hasattr(state.constraints, k):
                        setattr(state.constraints, k, v)

            if task.get("current_state_needs"):
                prior_needs = task["current_state_needs"]
                state.needs.flight = prior_needs.get("flight", False)
                state.needs.hotel = prior_needs.get("hotel", False)
                state.needs.activity = prior_needs.get("activity", False)

        # Set LLM cache scope to this task
        set_llm_task_id(task_id)

        if verbose:
            print(f"\n{'='*60}")
            print(f"[{task_id}] (Tier {tier}) {task.get('description', '')}")
            print(f"  Query: {user_query[:100]}{'...' if len(user_query)>100 else ''}")

        # --- 2. Orchestrator — detect needs ---
        task_json = {
            "task_id": task_id,
            "updated_constraints": expected.get("updated_constraints", {}),
        }

        analysis = analyze_user_input(
            user_msg=user_query,
            state=state,
            task_json=task_json,
        )
        state = update_state_from_analysis(state, analysis)
        result["analysis"] = analysis

        needs = state.needs
        if verbose:
            print(f"  Orchestrator → intent={analysis.get('intent')}, "
                  f"needs: flight={needs.flight}, hotel={needs.hotel}, activity={needs.activity}")

        # --- 3. Check if any need detected ---
        if not (needs.flight or needs.hotel or needs.activity):
            result["status"] = "skipped"
            result["error"] = "No needs detected — nothing to search"
            if verbose:
                print(f"  SKIPPED (no needs)")
            return result

        # --- 4. Search independently ---
        search_results = {"flights": [], "hotels": [], "activities": []}

        if needs.flight:
            if verbose:
                print(f"  Searching flights...")
            search_results["flights"] = search_flight_candidates(
                constraints=state.constraints, task_id=state.task_id,
            )

        if needs.hotel:
            if verbose:
                print(f"  Searching hotels...")
            search_results["hotels"] = search_hotel_candidates(
                constraints=state.constraints, task_id=state.task_id,
            )

        if needs.activity:
            if verbose:
                print(f"  Searching activities...")
            search_results["activities"] = search_activity_candidates(
                constraints=state.constraints, task_id=state.task_id,
            )

        if verbose:
            for cat, items in search_results.items():
                if items:
                    print(f"  [{cat}] {len(items)} search call(s)")

        # --- 5. Top-K selection with LLM ---
        if verbose:
            print(f"  Running top-K selection...")
        constraints_str = state.constraints.model_dump_json(indent=2)
        selection = select_top_k(
            task_id=state.task_id,
            constraints_json=constraints_str,
            needs=needs,
            search_results=search_results,
            top_k=5,
        )
        result["selection"] = selection

        # --- 6. Validate ---
        if verbose:
            print(f"  Validating plan...")
        validation = validate_plan(selection, state.constraints)
        result["validation"] = validation

        # --- 7. Save plan (always, even if constraints unmet) ---
        # Save the full LLM selection output (reasoning, constraints, itinerary)
        repo = PlanRepository()
        saved_path = repo.save_plan(plan=selection, task_id=state.task_id, save_metadata=True)

        # --- 8. Compare needs with expected ---
        expected_needs = expected.get("expected_needs", {})
        actual_needs = {"flight": needs.flight, "hotel": needs.hotel, "activity": needs.activity}
        needs_match = actual_needs == expected_needs if expected_needs else True
        result["needs_match"] = needs_match
        result["expected_needs"] = expected_needs
        result["actual_needs"] = actual_needs

        # Always count as success if plan was saved (evaluation handles scoring)
        result["status"] = "success"
        if validation["valid"]:
            if verbose:
                print(f"  ✓ SAVED (valid) → {saved_path}")
        else:
            result["unmet_constraints"] = validation.get("unmet_constraints", [])
            if verbose:
                print(f"  ⚠ SAVED (constraints unmet) → {saved_path}")

        if verbose and expected_needs:
            mark = "✓" if needs_match else "✗"
            print(f"  {mark} Needs match: expected={expected_needs} actual={actual_needs}")
            print(f"  Unmet: {validation.get('unmet_constraints', [])}")

        # Expose state for multi-turn chaining
        result["final_state"] = state

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        if verbose:
            print(f"  ERROR — {e}")
            traceback.print_exc()
    finally:
        set_llm_task_id(None)  # Reset so cache doesn't leak to next task

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


# ============================================================================
# Multi-Turn Runner (Tier 3)
# ============================================================================

def _group_multi_turn_tasks(tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group Tier 3 tasks by their base ID (e.g. ORCH-T3-01) and order by turn.
    Non-T3 tasks are returned as single-element groups.

    Returns:
        List of turn groups, e.g. [[turn1_task, turn2_task], [single_task]]
    """
    from collections import OrderedDict
    groups: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()

    for task in tasks:
        tid = task["task_id"]
        # Detect multi-turn pattern: ORCH-T3-XX-turnN
        if "-turn" in tid:
            base_id = tid.rsplit("-turn", 1)[0]   # "ORCH-T3-01"
        else:
            base_id = tid
        groups.setdefault(base_id, []).append(task)

    # Sort each group by turn number
    for base_id, group in groups.items():
        group.sort(key=lambda t: t["task_id"])

    return list(groups.values())


def run_multi_turn_task(
    turn_tasks: List[Dict[str, Any]],
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run a sequence of turn tasks with real state chaining.
    Turn 1 runs fresh; turn 2+ receives the final state from the previous turn.

    Args:
        turn_tasks: Ordered list of task dicts for the same conversation
                    (e.g. [ORCH-T3-01-turn1, ORCH-T3-01-turn2])
        verbose: Print progress

    Returns:
        List of result dicts, one per turn
    """
    results = []
    carry_state = None

    if verbose:
        base = turn_tasks[0]["task_id"].rsplit("-turn", 1)[0] if "-turn" in turn_tasks[0]["task_id"] else turn_tasks[0]["task_id"]
        print(f"\n{'#'*60}")
        print(f"  MULTI-TURN: {base} ({len(turn_tasks)} turns)")
        print(f"{'#'*60}")

    for i, task in enumerate(turn_tasks):
        if verbose and i > 0:
            print(f"\n  --- Carrying state from turn {i} → turn {i+1} ---")
            print(f"  Constraints: {carry_state.constraints.model_dump_json()}" if carry_state else "")
            print(f"  Needs: flight={carry_state.needs.flight}, hotel={carry_state.needs.hotel}, activity={carry_state.needs.activity}" if carry_state else "")

        r = run_single_task(task, verbose=verbose, prior_state=carry_state)
        results.append(r)

        # Carry state forward (even on error, to allow partial chaining)
        carry_state = r.get("final_state", carry_state)

    return results


# ============================================================================
# Batch Runner
# ============================================================================

def run_benchmark(
    tasks: List[Dict[str, Any]],
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run a list of orchestrator tasks and return results.
    Multi-turn tasks (Tier 3 with -turnN suffix) are automatically grouped
    and chained so that turn 1's real output state feeds into turn 2.
    """
    # Group multi-turn tasks; single tasks become 1-element groups
    groups = _group_multi_turn_tasks(tasks)
    total_tasks = sum(len(g) for g in groups)

    results = []
    print(f"\n{'#'*60}")
    print(f"  BENCHMARK: Running {total_tasks} tasks ({len(groups)} conversations)")
    print(f"{'#'*60}")

    task_idx = 0
    for group in groups:
        if len(group) > 1:
            # Multi-turn conversation — chain state
            turn_results = run_multi_turn_task(group, verbose=verbose)
            results.extend(turn_results)
            task_idx += len(group)
        else:
            task_idx += 1
            if verbose:
                print(f"\n[{task_idx}/{total_tasks}]", end="")
            r = run_single_task(group[0], verbose=verbose)
            results.append(r)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    invalid = sum(1 for r in results if r["status"] == "invalid")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    total_time = sum(r["elapsed_seconds"] for r in results)

    print(f"\n\n{'='*60}")
    print(f"BENCHMARK COMPLETE")
    print(f"  Total:   {total_tasks}")
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
    """Batch evaluate all saved plans with bootstrap CI, fractional CSR, and effect sizes."""
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

    if not results:
        return results

    # ── Collect per-task metrics ──
    overall_scores = []
    csr_scores = []
    tool_scores = []
    interest_scores = []
    binary_passes = []   # CSR == 1.0 → 1, else 0
    tier_scores: Dict[str, List[float]] = {}  # tier label → list of overall scores

    for task_id, r in sorted(results.items()):
        if "overall_score" not in r:
            continue
        os_val = r["overall_score"]
        csr_val = r.get("csr_score", 0)
        tool_val = r.get("tool_accuracy", 0)
        int_val = r.get("interest_score")  # None if no interests

        overall_scores.append(os_val)
        csr_scores.append(csr_val)
        tool_scores.append(tool_val)
        if int_val is not None:
            interest_scores.append(int_val)
        binary_passes.append(1 if csr_val >= 1.0 else 0)

        # Infer tier from task_id (e.g. ORCH-T1-02 → T1)
        parts = task_id.split("-")
        tier_label = parts[1] if len(parts) >= 2 else "unknown"
        tier_scores.setdefault(tier_label, []).append(os_val)

    if not overall_scores:
        return results

    n = len(overall_scores)

    # ── Bootstrap confidence intervals ──
    ci_overall = bootstrap_ci(overall_scores)
    ci_csr     = bootstrap_ci(csr_scores)
    ci_tools   = bootstrap_ci(tool_scores)

    # ── Effect sizes between tiers ──
    tier_labels = sorted(tier_scores.keys())
    effect_sizes = {}
    for i in range(len(tier_labels)):
        for j in range(i + 1, len(tier_labels)):
            key = f"{tier_labels[i]}_vs_{tier_labels[j]}"
            d = cohens_d(tier_scores[tier_labels[i]], tier_scores[tier_labels[j]])
            effect_sizes[key] = d

    # ── Print detailed results ──
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS  (n={n})")
    print(f"{'='*60}")

    # Per-task breakdown
    for task_id, r in sorted(results.items()):
        if "overall_score" in r:
            csr = r.get("csr_score", 0)
            binary = "PASS" if csr >= 1.0 else "FAIL"
            int_s = r.get("interest_score")
            int_str = f"  Interest={int_s:.1%}" if int_s is not None else ""
            print(f"\n  [{task_id}]  Overall={r['overall_score']:.1%}")
            print(f"    Schema={r.get('schema_compliance',0):.1%}  "
                  f"CSR(frac)={csr:.1%}  "
                  f"CSR(bin)={binary}  "
                  f"Tools={r.get('tool_accuracy',0):.1%}{int_str}")

    # Summary with bootstrap CI
    binary_rate = sum(binary_passes) / n
    print(f"\n{'-'*60}")
    print(f"AGGREGATE METRICS  (bootstrap 95% CI, 1000 resamples)")
    print(f"{'-'*60}")
    print(f"  Overall Score:  {ci_overall['mean']:.1%}  "
          f"[{ci_overall['ci_lower']:.1%}, {ci_overall['ci_upper']:.1%}]  "
          f"SD={ci_overall['std']:.3f}")
    print(f"  CSR (frac):     {ci_csr['mean']:.1%}  "
          f"[{ci_csr['ci_lower']:.1%}, {ci_csr['ci_upper']:.1%}]  "
          f"SD={ci_csr['std']:.3f}")
    print(f"  CSR (binary):   {binary_rate:.1%}  ({sum(binary_passes)}/{n} tasks fully satisfied)")
    print(f"  Tool Accuracy:  {ci_tools['mean']:.1%}  "
          f"[{ci_tools['ci_lower']:.1%}, {ci_tools['ci_upper']:.1%}]  "
          f"SD={ci_tools['std']:.3f}")
    if interest_scores:
        ci_int = bootstrap_ci(interest_scores)
        print(f"  Interest Score: {ci_int['mean']:.1%}  "
              f"[{ci_int['ci_lower']:.1%}, {ci_int['ci_upper']:.1%}]  "
              f"SD={ci_int['std']:.3f}  (n={len(interest_scores)} tasks with interests)")

    # Per-tier breakdown
    if len(tier_labels) > 1:
        print(f"\n  Per-Tier Overall Score:")
        for tl in tier_labels:
            ci_t = bootstrap_ci(tier_scores[tl])
            print(f"    {tl} (n={len(tier_scores[tl])}): "
                  f"{ci_t['mean']:.1%}  [{ci_t['ci_lower']:.1%}, {ci_t['ci_upper']:.1%}]")

    # Effect sizes
    if effect_sizes:
        print(f"\n  Effect Sizes (Cohen's d):")
        for key, d in effect_sizes.items():
            mag = "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
            print(f"    {key}: d={d:.3f} ({mag})")

    print(f"\n  Report: {report_file}")
    print(f"{'='*60}")

    # ── Save statistics alongside the evaluation report ──
    stats = {
        "n": n,
        "overall": ci_overall,
        "csr_fractional": ci_csr,
        "csr_binary_rate": round(binary_rate, 4),
        "tool_accuracy": ci_tools,
        "interest": bootstrap_ci(interest_scores) if interest_scores else None,
        "per_tier": {tl: bootstrap_ci(tier_scores[tl]) for tl in tier_labels},
        "effect_sizes": effect_sizes,
    }
    stats_path = report_file.replace(".json", "_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"  Stats saved: {stats_path}")

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
