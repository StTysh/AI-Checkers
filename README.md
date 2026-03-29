# AI-Checkers

AI-Checkers is a full-stack checkers playground for experimenting with classic board-game AI. It combines a FastAPI backend that manages game state and search algorithms with a React frontend for interactive play, benchmarking, and configuration.

## What it does

- Supports British (8x8) and International (10x10) checkers variants.
- Lets users play player-vs-player, player-vs-AI, and AI-vs-AI matches.
- Exposes configurable Minimax and MCTS agents with multiple search options.
- Includes evaluation tooling for running repeated AI matchups and exporting results.
- Provides a browser UI with animated gameplay, manual AI move confirmation, and session-based state.

## Core capabilities

### Minimax engine

- Alpha-beta pruning
- Transposition table support
- Move ordering and killer-move heuristics
- Quiescence search
- Iterative deepening
- Time-controlled search
- Parallel root search

### MCTS engine

- Parallel rollouts
- Guided rollouts
- Rollout cutoffs
- Hybrid leaf evaluation

### Frontend workflow

- Variant and game-mode selection
- Search parameter tuning from the UI
- Undo and reset controls
- Evaluation tab for automated agent benchmarking
- CSV and JSON export of AI-vs-AI runs

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

International example:

```bash
venv\Scripts\python.exe backend\bench\tune_heuristic.py --board-size 10 --iterative-deepening --time-limit-ms 1000 --depth 12 --games 20 --trials 100 --randomize-plies 4 --print-best
```

The script prints candidate evaluation profiles that can be applied to the backend heuristic configuration.

## Notes

- The backend stores session state in memory and assigns each browser session its own game state.
- The project is designed as an experimentation environment rather than a production service.
