# AI-Checkers

AI-Checkers is a capstone project focused on adversarial search in draughts. It combines a FastAPI backend, a React frontend, a reversible game engine for British 8x8 and International 10x10 rules, configurable minimax and MCTS agents, and an unattended AI-versus-AI evaluation workflow for repeatable experiments.

## What the project does

- Supports British 8x8 and International 10x10 draughts.
- Exposes human-versus-human, human-versus-AI, and AI-versus-AI play through a browser UI.
- Implements configurable minimax with alpha-beta, transposition tables, move ordering, quiescence, iterative deepening, time control, and related search options.
- Implements configurable MCTS with rollout-policy, leaf-evaluation, progressive widening, progressive bias, transposition, and parallelism controls.
- Supports staged AI moves, undo/reset, per-session recovery, and exportable evaluation results.
- Includes unattended manifest-driven batch runners for long AI-versus-AI experiments.

## Tech stack

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic

### Frontend

- Node.js 22.12.0 or newer compatible with Vite 7
- React 18
- Vite
- Material UI
- Zustand
- Vitest / Testing Library

## Repository structure

```text
backend/
  ai/        Search engines, heuristics, and transposition support
  bench/     Batch runners, manifests, tuning, and experiment tooling
  core/      Board model, move generation, rule handling, undo, hashing
  server/    FastAPI app, schemas, session layer, and API routes
  tests/     Backend regression and runtime tests
frontend/
  public/    Static assets
  src/       React pages, controls, hooks, and frontend tests
```

## Local setup

This repository is currently set up for Windows-first local development.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py --host 127.0.0.1 --port 8000 --reload
```

Equivalent Uvicorn entry point:

```bash
uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

For a more stable demo run without the development reloader:

```bash
python main.py --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies `/api` and `/docs` to the backend on `http://127.0.0.1:8000`.

For `npm run preview` or other static frontend serving, either put the frontend behind a reverse proxy that forwards `/api` and `/docs` to the backend, or build with explicit backend URLs:

```bash
cd frontend
$env:VITE_API_BASE="http://127.0.0.1:8000"
$env:VITE_DOCS_URL="http://127.0.0.1:8000/docs"
npm run build
npm run preview
```

## Testing and verification

### Backend tests

```bash
cd backend
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m pytest
```

### Frontend tests

```bash
cd frontend
npm ci
npm test
```

### Frontend production build

```bash
cd frontend
npm ci
npm run build
```

## Running experiments

The browser UI includes an AI-versus-AI evaluation panel for interactive experiment setup, live statistics, and CSV / JSON export.

For unattended runs, use the manifest runner in `backend/bench/`.

Example:

```bash
cd backend
venv\Scripts\python.exe bench\run_experiments.py --manifest bench\experiments.example.json --output-dir ..\output\evaluation_runs
```

Windows PowerShell wrappers for long report batches are also included, for example:

- `backend\bench\run_report_light_dataset.ps1`
- `backend\bench\run_eval_upgrade_24h.ps1`

These wrappers create timestamped output folders and stream logs while the manifest runner executes.

## Heuristic tuning

The backend includes a tuning script for empirical heuristic tuning via repeated mini-tournaments.

British 8x8 example:

```bash
cd backend
venv\Scripts\python.exe bench\tune_heuristic.py --board-size 8 --depth 6 --games 20 --trials 100 --randomize-plies 4 --print-best
```

International 10x10 example with iterative deepening:

```bash
cd backend
venv\Scripts\python.exe bench\tune_heuristic.py --board-size 10 --iterative-deepening --time-limit-ms 1000 --depth 12 --games 20 --trials 100 --randomize-plies 4 --print-best
```

The script prints a Python snippet for `_PROFILE_8` or `_PROFILE_10` that can be pasted into the heuristic profile module under `backend/ai/`.

## Notes

- Each browser session gets its own `GameSession`, and local runtime state is persisted for recovery after restart.
- Long evaluations are globally limited by `CHECKERS_MAX_GLOBAL_EVALUATIONS` to protect the demo machine from parallel browser sessions overloading it. The default is `1`.
- Frontend AI cancellation calls the backend `/api/ai-cancel` endpoint so stale AI workers do not commit after reset or configuration changes.
- The repository is intended as a coursework and experimentation environment rather than a production deployment target.
- Generated outputs under `output/` and runtime state under `.runtime/` are ignored by git.
