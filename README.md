# Nomad Travel Agent

Nomad is an AI travel-planning agent that combines Claude (Anthropic) and
SerpAPI to parse a user's travel request, search flights / hotels / activities,
filter candidates, verify the resulting plan against hard constraints, and
score it against a benchmark of orchestrator tasks (`NomadBench`).

The pipeline is decomposed into four layers:

```
Orchestrator → Specialist (search + Top-K) → Verifier → Evaluator
```

---

## Repository layout

```
Nomad_Travel_Agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── nomad/
    ├── src/                # Agent implementation
    │   ├── main.py         # Interactive CLI entry point
    │   ├── config.py       # Env vars, model, output dirs
    │   ├── state.py        # Travel state + constraint models
    │   ├── llm.py          # Claude API wrapper, structured output, cache
    │   ├── cache.py        # SerpAPI cache decorator
    │   ├── agents/
    │   │   ├── orchestrator.py   # Parse user input, detect needs
    │   │   ├── specialist.py     # Search, IATA resolution, Top-K + LLM select
    │   │   └── verifier.py       # Constraint validation + itinerary formatting
    │   ├── tools/
    │   │   ├── dispatch.py       # Tool registry + dispatcher
    │   │   ├── schemas.py        # SerpAPI tool schemas
    │   │   ├── serpapi.py        # SerpAPI manager (cache / snapshot / search)
    │   │   ├── plan_repository.py# Save / load plans
    │   │   ├── plan_schema.py    # Plan + evaluation schemas
    │   │   ├── evaluator.py      # Scoring engine
    │   │   └── auto_evaluator.py # Batch-evaluate saved plans
    │   ├── agent_test.ipynb            # Pipeline playground
    │   └── baseline_experiments.ipynb  # Vanilla LLM / RAG-only comparison
    ├── benchmark/
    │   ├── data/
    │   │   ├── orchestrator_tasks.json     # Main benchmark tasks
    │   │   ├── orchestrator_task_template.json
    │   │   ├── orchestrator_tasks_backup_v3.json
    │   │   └── tasks.json
    │   └── src/
    │       ├── run_benchmark.py            # Run pipeline + evaluate
    │       ├── run_baselines.py            # Vanilla + RAG-only baselines
    │       ├── t1_breakdown.py             # Per-task Tier-1 analysis
    │       ├── statistics.py               # Bootstrap CI, Cohen's d
    │       └── orchestrator_task_builder.py
    └── output/             # Generated at runtime (created by config.py)
        ├── cache/                  # SerpAPI response cache
        ├── llm_cache/              # Claude response cache (per task_id)
        ├── search_candidates/      # Saved candidate lists
        ├── verification_results/   # Verifier outputs
        ├── plans/                  # Nomad agent plans
        ├── plans_vanilla/          # Vanilla-LLM baseline plans
        ├── plans_rag/              # RAG-only baseline plans
        └── evaluations/            # Evaluation reports + stats
```

---

## Setup

### 1. Requirements

* Python ≥ **3.10** (tested on 3.10 / 3.11 / 3.14).
* An [Anthropic API key](https://console.anthropic.com/) and a
  [SerpAPI key](https://serpapi.com/).

### 2. Install dependencies

```bash
git clone https://github.com/yikouyi312/Nomad_Travel_Agent
cd Nomad_Travel_Agent
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
```

`requirements.txt`:

| Package         | Purpose                                                        |
| --------------- | -------------------------------------------------------------- |
| `requests`      | HTTP calls to Anthropic & SerpAPI                              |
| `python-dotenv` | Loads API keys from `.env` (see `nomad/src/config.py`)         |
| `pydantic`      | Constraint / state / plan models, structured-output validation |
| `jupyter`, `ipykernel` | Optional — only required for the two `.ipynb` notebooks |

### 3. Configure secrets

```bash
cp .env.example .env
# then edit .env and fill in:
#   CLAUDE_API_KEY=...
#   SERP_API=...
```

`nomad/src/config.py` loads `.env` automatically and raises on missing keys.

---

## How to run

All commands assume the repo root is the current directory.

### Interactive agent (single user session)

```bash
python nomad/src/main.py
```

Built-in commands inside the session:
* `save <name>` — persist current state
* `load <name>` — restore a saved session
* `sessions`    — list saved sessions
* `exit`        — quit

### Run the full benchmark

```bash
python nomad/benchmark/src/run_benchmark.py            # all tasks
python nomad/benchmark/src/run_benchmark.py --tier 1   # Tier-1 only
python nomad/benchmark/src/run_benchmark.py --task ORCH-T1-02   # single task
python nomad/benchmark/src/run_benchmark.py --evaluate-only     # skip agent, score saved plans
python nomad/benchmark/src/run_benchmark.py --no-evaluate       # run pipeline without scoring
```

Outputs:
* Plans → `nomad/output/plans/<task_id>/plan.json`
* Run log → `nomad/output/benchmark_run_log.json`
* Aggregate report → `nomad/output/evaluations/benchmark_evaluation.json`
* Bootstrap stats → `nomad/output/evaluations/benchmark_evaluation_stats.json`

### Run baselines (Vanilla LLM / RAG-only)

```bash
python nomad/benchmark/src/run_baselines.py                    # both baselines
python nomad/benchmark/src/run_baselines.py --baseline vanilla
python nomad/benchmark/src/run_baselines.py --baseline rag
python nomad/benchmark/src/run_baselines.py --tier 1
python nomad/benchmark/src/run_baselines.py --evaluate-only
```

Outputs:
* `nomad/output/plans_vanilla/<task_id>/plan.json`
* `nomad/output/plans_rag/<task_id>/plan.json`
* Comparison table printed to stdout
* `nomad/output/evaluations/baseline_comparison.json`

### Tier-1 per-task breakdown

```bash
python nomad/benchmark/src/t1_breakdown.py
```

Outputs:
* Pretty-printed table with overall / schema / CSR / tool / consistency
  scores and the failure type for each failing constraint.
* `nomad/output/evaluations/t1_breakdown.json`

---

## Reproducing experiments

Standard reproduction sequence:

```bash
# 1. Install + configure
pip install -r requirements.txt
cp .env.example .env && $EDITOR .env

# 2. Run the Nomad agent on every task and save plans
python nomad/benchmark/src/run_benchmark.py

# 3. Run both baselines (uses the same orchestrator tasks)
python nomad/benchmark/src/run_baselines.py

# 4. Per-task Tier-1 analysis
python nomad/benchmark/src/t1_breakdown.py
```

Reproducibility notes:

* **Caching**: SerpAPI responses (`output/cache/`) and Claude responses
  (`output/llm_cache/<task_id>/`) are cached on disk. A second run reuses cached
  results and is deterministic for everything except the live API surface.
  Delete the relevant cache subfolder to force fresh calls.
* **Random seeds**: `bootstrap_ci` in `benchmark/src/statistics.py` uses
  `random.Random(42)` so confidence intervals are reproducible across runs.
* **Selective re-runs**: `--task ORCH-T1-02` (or a Tier prefix) re-runs only
  the matching tasks; previously saved plans for other tasks are kept.
* **Score-only**: `--evaluate-only` re-scores saved plans without re-calling
  any APIs — useful while iterating on the evaluator.

---

## Evaluation scripts

| Script                                  | What it does                                                                                  |
| --------------------------------------- | --------------------------------------------------------------------------------------------- |
| `benchmark/src/run_benchmark.py`        | Runs the agent on benchmark tasks, then evaluates with bootstrap CI + per-tier + Cohen's *d*. |
| `benchmark/src/run_baselines.py`        | Runs Vanilla-LLM and RAG-only baselines and prints a side-by-side comparison.                 |
| `benchmark/src/t1_breakdown.py`         | Per-task Tier-1 detail: which constraints failed, mapped to failure types.                    |
| `benchmark/src/statistics.py`           | `bootstrap_ci(scores)` and `cohens_d(g1, g2)` helpers used by the runners.                    |
| `src/tools/auto_evaluator.py`           | Batch-loads saved plans and runs `NomadEvaluator.evaluate()` on each.                         |
| `src/tools/evaluator.py`                | Core scoring engine (Schema, CSR fractional/binary, Tool accuracy, Interest, Consistency).    |

Scoring formula (printed by `run_baselines.py`):

```
Overall = 0.9 × (0.35·CSR + 0.25·Schema + 0.20·Tool + 0.20·Consistency) + 0.10·Interest
```

---

## Pipeline summary

1. **`main.py`** reads user input.
2. **`agents.orchestrator`** parses intent, extracts/updates constraints,
   and detects flight / hotel / activity needs.
3. **`agents.specialist`** searches SerpAPI (via `tools.serpapi`), saves
   candidate results, and runs Top-K + LLM selection.
4. **`agents.verifier`** validates the selected plan against hard
   constraints and produces the final itinerary or a negotiation prompt.
5. Plans land in `output/plans/`, verification records in
   `output/verification_results/`, scores in `output/evaluations/`.

---

## Notebook guides

### `nomad/src/agent_test.ipynb`

Development playground for the full pipeline. Demonstrates:

* reloading local modules so notebook edits stay live,
* running a single benchmark task end-to-end (Orchestrator → Specialist → Verifier),
* evaluating the generated plan and printing the score summary,
* restoring a saved plan from `output/plans/`,
* running an entire tier of tasks,
* batch evaluation of saved plans,
* bootstrap statistics — 95 % CI, fractional/binary CSR, per-tier breakdown, Cohen's *d*,
* an explicit demo of parse → search → Top-K → validate → negotiate.

### `nomad/src/baseline_experiments.ipynb`

Compares Nomad against two baselines:

* **Vanilla LLM** — Orchestrator extracts constraints; Claude generates an
  itinerary from parametric memory only. No SerpAPI calls.
* **RAG-only** — Same search + selection pipeline as Nomad, but trusts the
  selector's `constraints_met` flag and saves `closest_alternative` when the
  selector reports failure.

Also covers shared helpers, baseline batch runs, evaluation, the comparison
table, and the Tier-1 per-task breakdown with failure-type analysis.

---

## Troubleshooting

| Symptom                                                     | Likely cause / fix                                                            |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `CLAUDE_API_KEY environment variable is missing.`           | `.env` is missing or in the wrong directory — must sit next to `README.md`.   |
| `SERP_API environment variable is missing.`                 | Same as above.                                                                |
| Benchmark hangs on the first task                           | First-time SerpAPI calls populate the cache; subsequent runs are much faster. |
| Want to force fresh API calls                               | Delete `nomad/output/cache/` and/or `nomad/output/llm_cache/<task_id>/`.      |
| `ModuleNotFoundError: agents` when running benchmark script | Run from the repo root — the script adds `nomad/src` to `sys.path` itself.    |
