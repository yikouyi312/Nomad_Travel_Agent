# Nomad Travel Agent

Nomad is an AI travel planning agent project that combines Claude and SerpAPI to parse travel requests, search flights/hotels/activities, filter candidates, verify plans, and evaluate results.

## Structure

- `src/`: Core agent implementation
  - `main.py`: Interactive command-line entry point. Handles multi-turn sessions, save/load state, and runs the pipeline: orchestrator, search, top-k selection, and verification.
  - `config.py`: Loads environment variables and defines global constants (API URLs, model, output directories, cache directories, etc.).
  - `state.py`: Defines travel constraints, needs, draft itinerary, and session persistence.
  - `llm.py`: Anthropic Claude integration, structured output helpers, task-scoped caching, and retry logic.
  - `cache.py`: SerpAPI response caching decorator to reuse API calls during benchmarks or repeated runs.
  - `agents/`: Agent layers
    - `orchestrator.py`: Parses user input, extracts/updates constraints, detects travel needs, and updates state.
    - `specialist.py`: Encapsulates candidate search, IATA airport resolution, top-k filtering, LLM selection, and legacy ReAct specialist compatibility.
    - `verifier.py`: Plan validation and formatting, including constraint checking, issue summarization, negotiation messaging, and final itinerary formatting.
  - `tools/`: Utility and infrastructure layer
    - `dispatch.py`: Tool registry and dispatch entry point.
    - `schemas.py`: SerpAPI tool schema definitions (flights, hotels, places).
    - `serpapi.py`: SerpAPI manager, cache handling, snapshot support, and actual search wrappers.
    - `plan_repository.py`: Save/load verified plans and repository management.
    - `auto_evaluator.py`: Automatic plan evaluation based on repository content.
    - `evaluator.py`: Evaluation engine implementation.
    - `plan_schema.py`: Plan and evaluation schema definitions.
    - `__init__.py`: Python package initialization.

- `benchmark/`: Benchmark and evaluation utilities
  - `benchmark/data/`: Task datasets, predefined tasks, and snapshot files.
    - `orchestrator_tasks.json`: Main benchmark task list.
    - `orchestrator_task_template.json`: Task template.
    - `orchestrator_tasks_backup_v3.json`: Backup task list.
    - `tasks.json`: Additional task definitions.
  - `benchmark/src/`: Benchmark scripts
    - `run_benchmark.py`: Main benchmark runner. Loads tasks and executes the pipeline by tier/task, with support for multi-turn conversations, search, selection, validation, and evaluation.
    - `run_baselines.py`: Runs Vanilla LLM and RAG-only baselines and compares scores.
    - `orchestrator_task_builder.py`: Helper tool to build orchestrator benchmark tasks.
    - `statistics.py`: Statistical utilities (bootstrap CI, Cohen's d, etc.).
    - `t1_breakdown.py`: Tier 1 task analysis and breakdown helper.

- `output/`: Runtime-generated artifacts (created by `config.py`)
  - `cache/`: SerpAPI cache files.
  - `llm_cache/`: LLM request cache files.
  - `verification_results/`: Saved verification outputs.
  - `search_candidates/`: Saved search candidates.
  - `plans/`: Saved verified plans.
  - `evaluations/`: Evaluation reports and results.
  - `plans_vanilla/`: Vanilla baseline plans.
  - `plans_rag/`: RAG-only baseline plans.

## Getting Started

### Environment setup

1. Create a `.env` file in the repository root.
2. Set the following environment variables:
   - `CLAUDE_API_KEY`
   - `SERP_API`

### Run interactively

```bash
python nomad/src/main.py
```

### Run benchmark

```bash
python nomad/benchmark/src/run_benchmark.py
```

Supported arguments:
- `--tier 1|2|3`
- `--task ORCH-T1-02`
- `--evaluate-only`
- `--no-evaluate`

### Run baseline comparison

```bash
python nomad/benchmark/src/run_baselines.py
```

## Core Pipeline

1. User input is read by `src/main.py`.
2. `agents.orchestrator` parses intent and constraints, and detects flight/hotel/activity needs.
3. `agents.specialist` uses `tools.serpapi` to search SerpAPI, save candidate results, then filter and select the best combination with Top-K + LLM.
4. `agents.verifier` validates the selected plan against hard constraints and generates the final itinerary or negotiation prompt.
5. Plans are saved under `output/plans/`, verification results under `output/verification_results/`, and evaluation outputs under `output/evaluations/`.

## Key Files

- `src/main.py`: Project entry point with `save` / `load` / `sessions` commands and the full agent pipeline.
- `src/config.py`: Centralized API key, model, directory, and cache configuration.
- `src/state.py`: Travel state objects, constraint models, and session persistence.
- `src/llm.py`: Claude API integration, cache key generation, cache handling, and structured JSON output support.
- `src/cache.py`: SerpAPI request caching decorator to reduce repeated API calls.
- `src/agents/orchestrator.py`: Large system prompt, analysis schema, and state update logic.
- `src/agents/specialist.py`: Candidate search persistence, IATA resolution, candidate filtering, Top-K selection, and legacy specialist compatibility.
- `src/agents/verifier.py`: Verification schema, itinerary formatting, constraint checks, and negotiation messaging.
- `src/tools/serpapi.py`: Core SerpAPI manager with local cache, snapshot, and search wrappers for flights/hotels/places.
- `src/tools/dispatch.py`: Tool execution entrypoint with backward-compatible interface.
- `src/tools/schemas.py`: Defines available tool input schemas.
- `src/tools/plan_repository.py`: Save and load plans as JSON.
- `src/tools/auto_evaluator.py`: Automatically read plans and invoke the evaluator.
- `benchmark/src/run_benchmark.py`: Main benchmark workflow script that runs the full agent pipeline.
- `benchmark/src/run_baselines.py`: Baseline comparison script for Vanilla LLM and RAG-only.

## Notes

- This repository is designed around a decomposed architecture: constraint layer, search layer, selection layer, and verification layer.
- All search results, verification records, and plan outputs are written to `output/`.
- Make sure your `.env` file contains valid API keys before running.
