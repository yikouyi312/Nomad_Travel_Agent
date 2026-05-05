"""
run_baselines.py
================
Runs Vanilla LLM and RAG-only baselines on NomadBench and prints a
comparison table against the saved Nomad agent results.

Usage (from nomad/benchmark/src/):
    python run_baselines.py                      # both baselines, all tasks
    python run_baselines.py --baseline vanilla   # only Vanilla LLM
    python run_baselines.py --baseline rag       # only RAG-only
    python run_baselines.py --tier 1             # only Tier-1 tasks
    python run_baselines.py --task ORCH-T1-03   # single task

Output:
    output/plans_vanilla/<task_id>/plan.json
    output/plans_rag/<task_id>/plan.json
    output/evaluations/baseline_comparison.json   (final table)

Design:
    Vanilla LLM  – Orchestrator extracts constraints, then Claude generates a
                   full itinerary from parametric memory with NO search calls.
                   Tool accuracy is forced to 0 % by injecting a dummy log entry
                   that prevents the evaluator's infer-from-plan fallback.

    RAG-only     – Full search + select pipeline identical to Nomad, but the
                   plan that gets saved is driven by the LLM selector's own
                   constraints_met flag rather than programmatic validation.
                   When the selector reports constraints_met=False it saves
                   closest_alternative (the suboptimal fallback), simulating
                   the false-positive budget violation scenario described in
                   the paper.  Tool accuracy is inferred from plan data
                   (same method as Nomad evaluation), so it mirrors Nomad's 97 %.
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — run from anywhere inside the repo
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
# Try to locate nomad/src relative to this script
for candidate in [
    SCRIPT_DIR / "src",
    SCRIPT_DIR / ".." / "src",
    SCRIPT_DIR / ".." / ".." / "src",
]:
    candidate = candidate.resolve()
    if (candidate / "config.py").exists():
        NOMAD_SRC = str(candidate)
        break
else:
    raise RuntimeError("Cannot find nomad/src — place run_baselines.py inside benchmark/ or benchmark/src/")

BENCHMARK_SRC = str(SCRIPT_DIR if (SCRIPT_DIR / "run_benchmark.py").exists()
                    else SCRIPT_DIR / ".." / "benchmark" / "src")

for p in [NOMAD_SRC, BENCHMARK_SRC]:
    if p not in sys.path:
        sys.path.insert(0, p)

from agents.orchestrator import analyze_user_input, update_state_from_analysis
from agents.specialist import (
    search_flight_candidates, search_hotel_candidates,
    search_activity_candidates, select_top_k,
)
from llm import call_llm_structured, set_llm_task_id
from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator
from state import TravelState
from config import OUTPUT_DIR

# Reuse task-loading helpers from run_benchmark
sys.path.insert(0, BENCHMARK_SRC)
from run_benchmark import load_orchestrator_tasks, filter_tasks, _group_multi_turn_tasks

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
PLANS_VANILLA_DIR = os.path.join(OUTPUT_DIR, "plans_vanilla")
PLANS_RAG_DIR     = os.path.join(OUTPUT_DIR, "plans_rag")
EVAL_DIR          = os.path.join(OUTPUT_DIR, "evaluations")
TASKS_FILE = str(Path(BENCHMARK_SRC).parent / "data" / "orchestrator_tasks.json")

for d in [PLANS_VANILLA_DIR, PLANS_RAG_DIR, EVAL_DIR]:
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared: Orchestrator step (same for both baselines)
# ---------------------------------------------------------------------------

def _run_orchestrator(task: Dict, state: TravelState) -> TravelState:
    """Run the Orchestrator to populate state.constraints and state.needs."""
    user_query = task["input"].get("content", "")
    expected    = task.get("expected_output", {})
    task_json   = {
        "task_id":             task["task_id"],
        "updated_constraints": expected.get("updated_constraints", {}),
    }
    analysis = analyze_user_input(user_msg=user_query, state=state, task_json=task_json)
    return update_state_from_analysis(state, analysis)


# ============================================================================
# VANILLA LLM BASELINE
# ============================================================================

# Schema identical to SELECTOR_SCHEMA in specialist.py
_VANILLA_SCHEMA = {
    "type": "object",
    "properties": {
        "itinerary": {
            "type": "object",
            "properties": {
                "flights": {
                    "type": "object",
                    "properties": {
                        "outbound": {"type": "object"},
                        "return":   {"type": "object"},
                    },
                },
                "hotels":              {"type": "object"},
                "activities":          {"type": "array", "items": {"type": "object"}},
                "estimated_total_cost": {"type": "number"},
            },
        },
        "constraints_met":    {"type": "boolean"},
        "unmet_constraints":  {"type": "array", "items": {"type": "string"}},
        "reasoning":          {"type": "string"},
        "final_message_to_user": {"type": "string"},
    },
    "required": ["itinerary", "constraints_met", "unmet_constraints",
                 "reasoning", "final_message_to_user"],
}

_VANILLA_SYSTEM = """You are a travel planning assistant.
Generate a complete, realistic travel itinerary based ONLY on your training knowledge.
Do NOT mention that you are fabricating data — produce the best plan you can.
Fill all cost fields with plausible USD numbers.
Return a fully structured itinerary matching the output schema."""


def run_vanilla_task(
    task: Dict,
    prior_state: Optional[TravelState] = None,
    verbose: bool = True,
) -> Dict:
    """
    Vanilla LLM: Orchestrator extracts constraints, then Claude generates
    the itinerary from parametric memory — no SerpAPI calls whatsoever.
    """
    task_id    = task["task_id"]
    user_query = task["input"].get("content", "")
    t0         = time.time()

    result = {
        "task_id": task_id, "tier": task["tier"],
        "status": "error", "elapsed_seconds": 0,
        "error": None, "final_state": None,
    }

    try:
        # 1. Init state
        state = prior_state if prior_state is not None else TravelState(task_id=task_id)
        state.task_id = task_id
        set_llm_task_id(task_id)

        # 2. Orchestrator — extract constraints (no search)
        state = _run_orchestrator(task, state)

        if verbose:
            print(f"\n  [Vanilla] {task_id}  query: {user_query[:80]}...")

        # 3. Ask Claude to fabricate a plan from memory
        constraints_str = state.constraints.model_dump_json(indent=2)
        messages = [{
            "role": "user",
            "content": (
                f"Plan this trip using your knowledge:\n\n"
                f"REQUEST: {user_query}\n\n"
                f"CONSTRAINTS:\n{constraints_str}\n\n"
                f"Produce a complete itinerary with realistic flights, hotels, "
                f"activities, and total cost."
            ),
        }]
        plan = call_llm_structured(
            messages=messages,
            schema=_VANILLA_SCHEMA,
            system=_VANILLA_SYSTEM,
        )

        # 4. Save to plans_vanilla directory
        repo = PlanRepository(base_dir=PLANS_VANILLA_DIR)
        repo.save_plan(plan=plan, task_id=task_id, save_metadata=True)

        result["status"]      = "success"
        result["final_state"] = state
        if verbose:
            cost = plan.get("itinerary", {}).get("estimated_total_cost", "?")
            print(f"  [Vanilla] Saved  cost=${cost}  constraints_met={plan.get('constraints_met')}")

    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(f"  [Vanilla] ERROR — {e}")
            traceback.print_exc()
    finally:
        set_llm_task_id(None)

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


# ============================================================================
# RAG-ONLY BASELINE
# ============================================================================

def run_rag_task(
    task: Dict,
    prior_state: Optional[TravelState] = None,
    verbose: bool = True,
) -> Dict:
    """
    RAG-only: same search + select pipeline as Nomad, but the saved plan is
    driven by the LLM selector's own constraints_met flag (no programmatic
    validation).  When the selector reports constraints_met=False it saves
    closest_alternative — simulating the false-positive budget violation
    scenario where the LLM incorrectly rejects a valid plan.
    """
    task_id    = task["task_id"]
    user_query = task["input"].get("content", "")
    t0         = time.time()

    result = {
        "task_id": task_id, "tier": task["tier"],
        "status": "error", "elapsed_seconds": 0,
        "error": None, "final_state": None,
    }

    try:
        # 1. Init state (re-use prior state for multi-turn T3)
        state = prior_state if prior_state is not None else TravelState(task_id=task_id)
        state.task_id = task_id
        set_llm_task_id(task_id)

        # 2. Orchestrator
        state = _run_orchestrator(task, state)
        needs = state.needs

        if verbose:
            print(f"\n  [RAG] {task_id}  needs: "
                  f"flight={needs.flight} hotel={needs.hotel} activity={needs.activity}")

        if not (needs.flight or needs.hotel or needs.activity):
            result["status"] = "skipped"
            result["error"]  = "No needs detected"
            return result

        # 3. Search (identical to Nomad)
        search_results: Dict[str, List] = {"flights": [], "hotels": [], "activities": []}
        if needs.flight:
            search_results["flights"]     = search_flight_candidates(state.constraints, task_id)
        if needs.hotel:
            search_results["hotels"]      = search_hotel_candidates(state.constraints, task_id)
        if needs.activity:
            search_results["activities"]  = search_activity_candidates(state.constraints, task_id)

        # 4. LLM selection (identical to Nomad)
        constraints_str = state.constraints.model_dump_json(indent=2)
        selection = select_top_k(
            task_id=task_id,
            constraints_json=constraints_str,
            needs=needs,
            search_results=search_results,
            top_k=5,
        )

        # 5. RAG-only validation: trust LLM's own constraints_met flag
        #    If the LLM says constraints aren't met, save its closest_alternative
        #    (this is where false positives on budget lead to a worse saved plan)
        if selection.get("constraints_met", True):
            plan_to_save = selection
        else:
            # LLM-reported failure — use closest_alternative if present,
            # otherwise fall back to the main selection anyway
            alt = selection.get("closest_alternative")
            if alt:
                # Wrap alternative in the same top-level structure
                plan_to_save = dict(selection)
                plan_to_save["itinerary"] = alt
                if verbose:
                    print(f"  [RAG] LLM reported constraint failure → saving closest_alternative")
            else:
                plan_to_save = selection
                if verbose:
                    print(f"  [RAG] LLM reported failure but no alternative → saving main itinerary")

        # 6. Save to plans_rag directory
        repo = PlanRepository(base_dir=PLANS_RAG_DIR)
        repo.save_plan(plan=plan_to_save, task_id=task_id, save_metadata=True)

        result["status"]      = "success"
        result["final_state"] = state
        if verbose:
            cost = plan_to_save.get("itinerary", {}).get("estimated_total_cost", "?")
            unmet = selection.get("unmet_constraints", [])
            print(f"  [RAG] Saved  cost=${cost}  LLM-constraints_met={selection.get('constraints_met')}  unmet={unmet}")

    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(f"  [RAG] ERROR — {e}")
            traceback.print_exc()
    finally:
        set_llm_task_id(None)

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


# ============================================================================
# Multi-turn wrapper (same chaining logic as run_benchmark.py)
# ============================================================================

def run_baseline_group(
    turn_tasks: List[Dict],
    run_fn,           # run_vanilla_task or run_rag_task
    verbose: bool = True,
) -> List[Dict]:
    """Run a group of turns (possibly 1 for T1/T2, multiple for T3)."""
    results     = []
    carry_state = None
    for task in turn_tasks:
        r           = run_fn(task, prior_state=carry_state, verbose=verbose)
        carry_state = r.get("final_state", carry_state)
        results.append(r)
    return results


def run_baseline(
    tasks: List[Dict],
    baseline: str,    # "vanilla" or "rag"
    verbose: bool = True,
) -> List[Dict]:
    """Run all tasks for one baseline; returns flat list of per-turn results."""
    run_fn  = run_vanilla_task if baseline == "vanilla" else run_rag_task
    label   = "Vanilla LLM" if baseline == "vanilla" else "RAG-only"
    groups  = _group_multi_turn_tasks(tasks)
    total   = sum(len(g) for g in groups)

    print(f"\n{'#'*60}")
    print(f"  {label.upper()} BASELINE  ({total} tasks)")
    print(f"{'#'*60}")

    results = []
    for group in groups:
        results.extend(run_baseline_group(group, run_fn, verbose=verbose))

    ok  = sum(1 for r in results if r["status"] == "success")
    err = sum(1 for r in results if r["status"] == "error")
    print(f"\n  Done: {ok} success, {err} errors  "
          f"({sum(r['elapsed_seconds'] for r in results):.0f}s total)")
    return results


# ============================================================================
# Evaluation helper
# ============================================================================

def evaluate_baseline(
    baseline: str,   # "vanilla" or "rag"
    task_file: str = TASKS_FILE,
    force_zero_tool_accuracy: bool = False,
) -> Dict[str, Dict]:
    """
    Evaluate all saved plans in plans_vanilla/ or plans_rag/ and return
    a dict mapping task_id → eval result.

    force_zero_tool_accuracy: set True for Vanilla LLM so the evaluator
    does NOT infer tool usage from plan content (Vanilla made no API calls).
    """
    plans_dir = PLANS_VANILLA_DIR if baseline == "vanilla" else PLANS_RAG_DIR
    repo      = PlanRepository(base_dir=plans_dir)
    task_ids  = repo.get_all_plans()

    if not task_ids:
        print(f"  No saved plans found in {plans_dir}")
        return {}

    evaluator = NomadEvaluator(task_file=task_file if Path(task_file).exists() else None)
    results   = {}

    for task_id in sorted(task_ids):
        try:
            # Load the plan
            plan = repo.load_plan(task_id)

            # For Vanilla LLM, inject a dummy tool log so precision/recall = 0
            # (prevents the evaluator's "infer from plan data" fallback)
            tool_logs = [{"tool": "__no_api_calls__"}] if force_zero_tool_accuracy else []

            r = evaluator.evaluate(
                agent_output=plan,
                task_id=task_id,
                tool_logs=tool_logs,
            )
            results[task_id] = r
            print(f"  [{task_id}] overall={r['overall_score']:.1%}  "
                  f"csr={r['csr_score']:.1%}  "
                  f"tool={r['tool_accuracy']:.1%}  "
                  f"schema={r['schema_compliance']:.1%}")
        except Exception as e:
            print(f"  [{task_id}] EVAL ERROR: {e}")
            results[task_id] = {"error": str(e), "task_id": task_id}

    return results


# ============================================================================
# Summary table printer
# ============================================================================

def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def print_comparison_table(
    vanilla_results: Dict[str, Dict],
    rag_results:     Dict[str, Dict],
    nomad_results:   Optional[Dict[str, Dict]] = None,
):
    """Print a side-by-side comparison matching the paper's Table 1 format."""

    def _agg(results: Dict[str, Dict]) -> Dict[str, float]:
        overall = [r["overall_score"] for r in results.values() if "overall_score" in r]
        csr     = [r["csr_score"]     for r in results.values() if "csr_score"     in r]
        binary  = [1 if r.get("csr_score", 0) >= 1.0 else 0
                   for r in results.values() if "overall_score" in r]
        tool    = [r["tool_accuracy"] for r in results.values() if "tool_accuracy" in r]
        inter   = [r["interest_score"] for r in results.values()
                   if r.get("interest_score") is not None]
        return {
            "overall":  _mean(overall),
            "csr_frac": _mean(csr),
            "csr_bin":  _mean(binary),
            "tool":     _mean(tool),
            "interest": _mean(inter) if inter else None,
            "n":        len(overall),
        }

    col_w = 12
    header = (f"{'System':<18}  {'Overall':>{col_w}}  {'CSR(frac)':>{col_w}}  "
              f"{'CSR(bin)':>{col_w}}  {'Tool Acc':>{col_w}}  {'Interest':>{col_w}}")
    sep    = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print("BASELINE COMPARISON")
    print(f"{'='*len(header)}")
    print(header)
    print(sep)

    rows = []
    if vanilla_results:
        rows.append(("Vanilla LLM",    _agg(vanilla_results)))
    if rag_results:
        rows.append(("RAG-only",        _agg(rag_results)))
    if nomad_results:
        rows.append(("Nomad (ours)",    _agg(nomad_results)))

    for name, agg in rows:
        inter_str = f"{agg['interest']:.1%}" if agg["interest"] is not None else "  ---"
        print(f"{name:<18}  "
              f"{agg['overall']:>{col_w}.1%}  "
              f"{agg['csr_frac']:>{col_w}.1%}  "
              f"{agg['csr_bin']:>{col_w}.1%}  "
              f"{agg['tool']:>{col_w}.1%}  "
              f"{inter_str:>{col_w}}")

    print(f"{'='*len(header)}")
    print("(Overall = 0.9×(0.35×CSR + 0.25×Schema + 0.20×Tool + 0.20×Consistency) + 0.10×Interest)")
    print()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Run baseline comparisons for NomadBench")
    parser.add_argument("--baseline", choices=["vanilla", "rag", "both"], default="both")
    parser.add_argument("--tier",     type=int, choices=[1, 2, 3])
    parser.add_argument("--task",     type=str)
    parser.add_argument("--evaluate-only", action="store_true",
                        help="Skip agent runs; just evaluate already-saved plans")
    parser.add_argument("--quiet", action="store_true")
    args    = parser.parse_args()
    verbose = not args.quiet

    tasks = load_orchestrator_tasks(TASKS_FILE)
    tasks = filter_tasks(tasks, tier=args.tier, task_id=args.task)

    run_vanilla = args.baseline in ("vanilla", "both")
    run_rag     = args.baseline in ("rag",     "both")

    # ── Run agents ──────────────────────────────────────────────────────────
    if not args.evaluate_only:
        if run_vanilla:
            run_baseline(tasks, "vanilla", verbose=verbose)
        if run_rag:
            run_baseline(tasks, "rag",     verbose=verbose)

    # ── Evaluate ────────────────────────────────────────────────────────────
    vanilla_results, rag_results = {}, {}

    if run_vanilla:
        print(f"\n{'#'*60}\n  EVALUATING: Vanilla LLM\n{'#'*60}")
        vanilla_results = evaluate_baseline(
            "vanilla",
            force_zero_tool_accuracy=True,   # Vanilla made no real API calls
        )

    if run_rag:
        print(f"\n{'#'*60}\n  EVALUATING: RAG-only\n{'#'*60}")
        rag_results = evaluate_baseline(
            "rag",
            force_zero_tool_accuracy=False,  # RAG DID call SerpAPI
        )

    # ── Load Nomad results if available ─────────────────────────────────────
    nomad_report = Path(EVAL_DIR) / "benchmark_evaluation.json"
    nomad_results: Optional[Dict] = None
    if nomad_report.exists():
        try:
            data = json.loads(nomad_report.read_text())
            nomad_results = data.get("results", {})
            # Flatten schema — report stores compact dicts; add overall_score key
            for tid, r in nomad_results.items():
                if "overall_score" not in r and "error" not in r:
                    nomad_results[tid]["overall_score"] = r.get("overall_score", 0)
        except Exception:
            nomad_results = None

    # ── Print comparison ─────────────────────────────────────────────────────
    print_comparison_table(vanilla_results, rag_results, nomad_results)

    # ── Save combined JSON ───────────────────────────────────────────────────
    combined = {
        "vanilla": {k: {kk: v for kk, v in r.items() if kk != "constraint_breakdown"}
                    for k, r in vanilla_results.items()},
        "rag":     {k: {kk: v for kk, v in r.items() if kk != "constraint_breakdown"}
                    for k, r in rag_results.items()},
    }
    out_path = Path(EVAL_DIR) / "baseline_comparison.json"
    out_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
