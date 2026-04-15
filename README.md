# AI-Checkers

AI-Checkers is a full-stack checkers playground for experimenting with classic board-game AI. It combines a FastAPI backend that manages game state and search algorithms with a React frontend for interactive play, benchmarking, and configuration.

### Features
- British (8x8) and International (10x10) variants.
- Minimax with feature toggles (alpha-beta, TT, move ordering, killer moves, quiescence), iterative deepening, time control, and parallel root search.
- MCTS with parallel rollouts, guided rollouts, rollout cutoff, and hybrid leaf evaluation.
- Game modes: PvP, PvAI, AIvAI.
- Evaluation tooling (AIvAI tab): auto-play N games, live stats, CSV/JSON export.
- Animated pieces, undo/reset, manual AI move confirmation.

## Stack

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic

### Frontend

- React
- Vite
- Material UI
- Zustand

## Repository structure

```text
backend/
  ai/        Search engines, heuristics, and benchmarking scripts
  core/      Board representation, pieces, move rules, and session logic
  server/    FastAPI application, API schemas, and request handling
frontend/
  src/       React UI, dialogs, controls, and evaluation screens
```

## Running locally

This repository is currently set up for Windows-first local development.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

Alternative entry point:

```bash
python main.py --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs against the backend API on `http://127.0.0.1:8000`.

## Usage

1. Start the backend and frontend.
2. Open the frontend in the browser.
3. Choose a ruleset, game mode, and AI configuration.
4. Use the evaluation tab to run repeated AI matchups and export results.

## Heuristic tuning

The backend includes a tuning script for empirically testing heuristic weights with mini-tournaments:

```bash
venv\Scripts\python.exe backend\bench\tune_heuristic.py --board-size 8 --depth 6 --games 20 --trials 100 --randomize-plies 4 --print-best
```

International (10x10) example (time-budgeted via iterative deepening):
```bash
venv\Scripts\python.exe backend\bench\tune_heuristic.py --board-size 10 --iterative-deepening --time-limit-ms 1000 --depth 12 --games 20 --trials 100 --randomize-plies 4 --print-best
```

The script prints a Python snippet for `_PROFILE_8` / `_PROFILE_10` that you can paste into the heuristic profile module under `backend/ai/`.

## Notes

- The backend assigns each browser session its own game state and persists local runtime state for recovery after restart.
- The project is designed as an experimentation environment rather than a production service.
