## Checkers AI Playground

Modern FastAPI + React playground for experimenting with competitive checkers agents.

### Highlights
- British (8x8) and International (10x10) variants powered by a shared `core` engine.
- Advanced minimax with transposition table, killer-move ordering, and quiescence; simple minimax kept for A/B tests.
- Rich heuristic (`backend/ai/huistic.py`) rewarding material, mobility, promotion threats, edges, chain support, and capture pressure.
- REST session API supporting human players, queued AI moves, undo, and configurable controllers per color.
- Vite + React UI with animated pieces, theme switching, and live AI status.

### Requirements
- Python 3.11+
- Node.js 18+

### Backend
```bash
cd backend
python -m venv venv && venv/Scripts/activate  # Windows path shown
pip install -r requirements.txt
python main.py --host 127.0.0.1 --port 8000 --reload
```
Key modules:
- `server/session.py` – thread-safe orchestrator with pending-move queueing.
- `ai/minimax.py` – feature-rich search controller.
- `ai/simple_minimax.py` – baseline search for comparisons.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
The dev server proxies API calls to the backend; adjust Vite config if you change the port.

### Typical workflow
1. Start the backend (FastAPI + Uvicorn).
2. Start the frontend and open the printed URL.
3. Assign controllers per color (Human, Minimax, Minimax Simple) and tweak options such as depth, TT usage, and quiescence.
4. Watch real-time move annotations, pending AI moves, and restart or undo through the UI.

### Testing & troubleshooting
- Use `python -m pytest` inside `backend` (tests live under `backend/tests`).
- Clear transposition tables between games via the API if you hot-swap controller colors.
- For deterministic debugging set `PYTHONHASHSEED=0` and rely on the fixed Zobrist seed in `core/hash.py`.

### Project structure (excerpt)
```
backend/
	ai/              # heuristics + controllers
	core/            # board, pieces, move logic
	server/          # FastAPI wiring
frontend/
	src/             # React app (Board, Controls, Dialogs)
```

This README intentionally stays short (<100 lines). Consult inline module docs for deeper dives into heuristics, move ordering, and UI components.
