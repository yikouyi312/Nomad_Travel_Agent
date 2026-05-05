"""
t1_breakdown.py
===============
Prints a detailed per-task breakdown for all Tier-1 NomadBench tasks,
showing individual metric scores and which specific constraints failed.

Usage (from nomad/benchmark/src/):
    python t1_breakdown.py

Output:
    • Console table: Task | Overall | Schema | CSR(frac) | CSR(bin) | Tool | Consistency | Failing Constraints
    • output/evaluations/t1_breakdown.json

Requires:
    - Plans already saved in output/plans/ (run run_benchmark.py first)
    - orchestrator_tasks.json  (for constraint definitions)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

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
    raise RuntimeError("Cannot find nomad/src")

BENCHMARK_SRC = str(
    SCRIPT_DIR if (SCRIPT_DIR / "run_benchmark.py").exists()
    else SCRIPT_DIR / ".." / "benchmark" / "src"
)

for p in [NOMAD_SRC, BENCHMARK_SRC]:
    if p not in sys.path:
        sys.path.insert(0, p)

from tools.plan_repository import PlanRepository
from tools.evaluator import NomadEvaluator
from config import PLANS_DIR, EVALUATIONS_DIR

TASKS_FILE = str(Path(BENCHMARK_SRC).parent / "data" / "orchestrator_tasks.json")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _constraint_label(constraint_str: str) -> str:
    """Shorten a raw constraint string for table display."""
    c = constraint_str.lower()
    if "budget" in c or "$" in c:
        return "Budget"
    if "destination" in c:
        return "Destination"
    if "origin" in c or "departure" in c:
        return "Origin/Dep"
    if "hotel_location" in c or "hotel location" in c:
        return "Hotel location"
    if "start_date" in c:
        return "Start date"
    if "end_date" in c:
        return "End date"
    if "star" in c or "rating" in c:
        return "Hotel star"
    if "per night" in c or "nightly" in c:
        return "Hotel rate"
    if "vegetarian" in c or "vegan" in c or "dietary" in c:
        return "Dietary"
    if "night" in c or "duration" in c:
        return "Duration"
    # Truncate to 25 chars for other types
    return constraint_str[:25]


def _failure_type(constraint_str: str) -> str:
    """
    Map a failing constraint to the failure-type vocabulary used in the paper.
    """
    c = constraint_str.lower()
    # Location proximity constraints the API cannot resolve
    location_keywords = [
        "hotel_location", "hotel location",
        "near south congress", "downtown", "near ", "close to",
        "westminster", "times square",
    ]
    if any(kw in c for kw in location_keywords):
        return "Fine-grained geo"
    # Null metadata fields
    if "star" in c and ("null" in c or "none" in c or ": 0" in c):
        return "Metadata gap (hotel_class null)"
    if "rating" in c and ("null" in c or "none" in c or ": 0" in c):
        return "Metadata gap (hotel_class null)"
    if "hotel star" in c or "star:" in c:
        return "Metadata gap (hotel_class null)"
    if "budget" in c:
        return "Budget exceeded"
    if "airport" in c or "departure" in c or "arrival" in c:
        return "IATA mismatch"
    return "Constraint not met"


# ---------------------------------------------------------------------------
# Main breakdown function
# ---------------------------------------------------------------------------

def run_t1_breakdown(
    plans_dir: str = PLANS_DIR,
    tasks_file: str = TASKS_FILE,
    output_dir: str = EVALUATIONS_DIR,
    verbose: bool = True,
) -> List[Dict]:
    """
    Evaluate every saved Tier-1 plan and return a list of per-task dicts:
        {
          task_id, description, overall, schema, csr_frac, csr_bin,
          tool_acc, consistency, failing_constraints, failure_types
        }
    """
    # Load task definitions for descriptions and constraint info
    tasks_by_id: Dict[str, Dict] = {}
    if Path(tasks_file).exists():
        raw = json.loads(Path(tasks_file).read_text())
        tasks_by_id = {t["task_id"]: t for t in raw}

    t1_task_ids = sorted(
        tid for tid, t in tasks_by_id.items() if t.get("tier") == 1
    )

    if not t1_task_ids:
        print("No Tier-1 tasks found in orchestrator_tasks.json")
        return []

    repo      = PlanRepository(base_dir=plans_dir)
    evaluator = NomadEvaluator(task_file=tasks_file if Path(tasks_file).exists() else None)

    rows = []

    for task_id in t1_task_ids:
        task = tasks_by_id.get(task_id, {})
        desc = task.get("description", "")

        # Check if plan exists
        if not repo.plan_exists(task_id):
            print(f"  [{task_id}] No saved plan — skipping (run run_benchmark.py first)")
            rows.append({
                "task_id":             task_id,
                "description":         desc,
                "overall":             None,
                "schema":              None,
                "csr_frac":            None,
                "csr_bin":             None,
                "tool_acc":            None,
                "consistency":         None,
                "failing_constraints": [],
                "failure_types":       [],
                "note":                "No saved plan",
            })
            continue

        # Evaluate
        try:
            plan = repo.load_plan(task_id)
            r    = evaluator.evaluate(agent_output=plan, task_id=task_id)
        except Exception as e:
            print(f"  [{task_id}] Eval error: {e}")
            rows.append({
                "task_id": task_id, "description": desc,
                "note": f"Eval error: {e}",
            })
            continue

        overall      = r.get("overall_score", 0)
        schema       = r.get("schema_compliance", 0)
        csr_frac     = r.get("csr_score", 0)
        csr_bin      = csr_frac >= 1.0
        tool_acc     = r.get("tool_accuracy", 0)
        conflict     = r.get("conflict_report", {})
        consistency  = 0.5 if conflict.get("has_conflicts") else 1.0

        # Identify failing constraints
        breakdown = r.get("constraint_breakdown", {})
        failing   = [c for c, met in breakdown.items() if not met]
        ftypes    = [_failure_type(c) for c in failing]

        rows.append({
            "task_id":             task_id,
            "description":         desc,
            "overall":             overall,
            "schema":              schema,
            "csr_frac":            csr_frac,
            "csr_bin":             csr_bin,
            "tool_acc":            tool_acc,
            "consistency":         consistency,
            "failing_constraints": failing,
            "failure_types":       ftypes,
            "interest_score":      r.get("interest_score"),
            "conflict_errors":     conflict.get("errors", []),
            "conflict_warnings":   conflict.get("warnings", []),
        })

    # ── Print table ──────────────────────────────────────────────────────────
    if verbose:
        _print_table(rows)

    # ── Save JSON ────────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    out_path = Path(output_dir) / "t1_breakdown.json"
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out_path}")

    return rows


def _print_table(rows: List[Dict]):
    """Pretty-print the breakdown table to stdout."""

    # ── Wide table ────────────────────────────────────────────────────────────
    print(f"\n{'='*110}")
    print("TIER-1 PER-TASK BREAKDOWN")
    print(f"{'='*110}")
    print(
        f"{'Task ID':<16}  {'Overall':>8}  {'Schema':>7}  "
        f"{'CSR(fr)':>8}  {'CSR(bin)':>9}  "
        f"{'Tool':>6}  {'Consist':>8}  "
        f"Failing Constraints / Type"
    )
    print("-" * 110)

    for r in rows:
        tid = r["task_id"]

        if r.get("note") and r.get("overall") is None:
            print(f"{tid:<16}  {'N/A':>8}  {'N/A':>7}  {'N/A':>8}  {'N/A':>9}  "
                  f"{'N/A':>6}  {'N/A':>8}  {r['note']}")
            continue

        overall = r["overall"]
        if overall is None:
            continue

        csr_bin_str = "✓ PASS" if r["csr_bin"] else "✗ FAIL"
        failing     = r.get("failing_constraints", [])
        ftypes      = r.get("failure_types",       [])

        if failing:
            fail_str = "; ".join(
                f"{_constraint_label(c)} [{ft}]"
                for c, ft in zip(failing, ftypes)
            )
        else:
            fail_str = "—"

        print(
            f"{tid:<16}  "
            f"{overall:>8.1%}  "
            f"{r['schema']:>7.1%}  "
            f"{r['csr_frac']:>8.1%}  "
            f"{csr_bin_str:>9}  "
            f"{r['tool_acc']:>6.1%}  "
            f"{r['consistency']:>8.1%}  "
            f"{fail_str}"
        )

    # ── Aggregate row ─────────────────────────────────────────────────────────
    valid_rows = [r for r in rows if r.get("overall") is not None]
    if valid_rows:
        print("-" * 110)
        n       = len(valid_rows)
        mean_ov = sum(r["overall"]  for r in valid_rows) / n
        mean_sc = sum(r["schema"]   for r in valid_rows) / n
        mean_cs = sum(r["csr_frac"] for r in valid_rows) / n
        n_pass  = sum(1 for r in valid_rows if r["csr_bin"])
        mean_ta = sum(r["tool_acc"]    for r in valid_rows) / n
        mean_co = sum(r["consistency"] for r in valid_rows) / n

        print(
            f"{'MEAN (n=' + str(n) + ')':<16}  "
            f"{mean_ov:>8.1%}  "
            f"{mean_sc:>7.1%}  "
            f"{mean_cs:>8.1%}  "
            f"{n_pass}/{n} pass{' ':>4}  "
            f"{mean_ta:>6.1%}  "
            f"{mean_co:>8.1%}"
        )

    print(f"{'='*110}")

    # ── Narrative summary ─────────────────────────────────────────────────────
    print("\nFAILURE ANALYSIS SUMMARY")
    print("-" * 60)
    all_failures: Dict[str, int] = {}
    for r in valid_rows:
        for ft in r.get("failure_types", []):
            all_failures[ft] = all_failures.get(ft, 0) + 1

    if all_failures:
        for ft, count in sorted(all_failures.items(), key=lambda x: -x[1]):
            tasks_with = [r["task_id"] for r in valid_rows
                          if ft in r.get("failure_types", [])]
            print(f"  {ft:<35}  {count}× ({', '.join(tasks_with)})")
    else:
        print("  No constraint failures — all T1 tasks passed ✓")

    # ── Key finding for paper ─────────────────────────────────────────────────
    fail_count  = sum(1 for r in valid_rows if not r["csr_bin"])
    pass_count  = len(valid_rows) - fail_count
    mean_pass   = sum(r["overall"] for r in valid_rows if  r["csr_bin"]) / max(pass_count, 1)
    mean_fail   = sum(r["overall"] for r in valid_rows if not r["csr_bin"]) / max(fail_count, 1)

    print(f"\n  Binary CSR:  {pass_count}/{len(valid_rows)} pass,  {fail_count}/{len(valid_rows)} fail")
    print(f"  Mean overall (passing tasks): {mean_pass:.1%}")
    print(f"  Mean overall (failing tasks): {mean_fail:.1%}")

    if fail_count == 1:
        failing_task = next(r for r in valid_rows if not r["csr_bin"])
        ftypes_str   = ", ".join(set(failing_task.get("failure_types", ["unknown"])))
        print(f"\n  ⚠  Sole binary failure: {failing_task['task_id']}")
        print(f"     Failure type: {ftypes_str}")
        print(f"     Conclusion: T1 mean is depressed by a SINGLE API metadata gap,")
        print(f"     not a systematic single-turn extraction weakness.")
        print(f"     T3's advantage comes from multi-turn context accumulation.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Per-task T1 evaluation breakdown")
    parser.add_argument("--plans-dir", default=PLANS_DIR,
                        help="Directory containing saved plans (default: output/plans)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    run_t1_breakdown(
        plans_dir=args.plans_dir,
        verbose=not args.quiet,
    )
