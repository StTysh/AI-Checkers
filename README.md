## Checkers AI Playground

FastAPI + React playground for competitive checkers agents on Windows.

### Features
- British (8×8) and International (10×10) variants.
- Minimax with feature toggles (alpha–beta, TT, move ordering, killer moves, quiescence), iterative deepening, time control, and parallel root search.
- MCTS with parallel rollouts, guided rollouts, rollout cutoff, and hybrid leaf evaluation.
- Game modes: PvP, PvAI, AIvAI.
- Evaluation tooling (AIvAI tab): auto-play N games, live stats, CSV/JSON export.
- Animated pieces, undo/reset, theme switcher, manual AI move confirmation.

### Requirements (Windows only)
- Python 3.11+
- Node.js 18+

### Backend (Windows)
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

Alternative (same result):
```bash
python main.py --host 127.0.0.1 --port 8000 --reload
```

### Frontend (Windows)
```bash
cd frontend
npm install
npm run dev
```

### Usage
1. Start backend and frontend.
2. In Play tab, choose game mode, variant, and AI settings.
3. In AI vs AI mode, open Evaluate tab to run experiments and export results.

### Project structure (excerpt)
```
backend/
  ai/              # heuristics + controllers
  core/            # board, pieces, move logic
  server/          # FastAPI wiring
frontend/
  src/             # React app (Board, Controls, Dialogs)
```

### Heuristic tuning (experimental)
You can empirically search for better heuristic weights by running mini-tournaments (candidate vs baseline) and mutating the `EvalProfile` values used by Minimax:

```bash
venv\Scripts\python.exe backend\bench\tune_heuristic.py --board-size 8 --depth 6 --games 20 --trials 100 --randomize-plies 4 --print-best
```

International (10Ã—10) example (time-budgeted via iterative deepening):
```bash
venv\Scripts\python.exe backend\bench\tune_heuristic.py --board-size 10 --iterative-deepening --time-limit-ms 1000 --depth 12 --games 20 --trials 100 --randomize-plies 4 --print-best
```

The script prints a Python snippet for `_PROFILE_8` / `_PROFILE_10` that you can paste into `backend/ai/huistic.py`.
