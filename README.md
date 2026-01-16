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
pip install -r requrements.txt
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
