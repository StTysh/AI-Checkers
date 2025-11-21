## Checkers AI Playground

### Quick start

```bash
python main.py --white human --black minimax --minimax-depth 5 --ai-move-delay 500
```

- `--white` / `--black`: choose `human` or `minimax` for each color.
- `--minimax-depth`: search depth for every minimax controller.
- `--ai-move-delay`: pause (ms) before an AI moves so you can follow along; set to `0` for instant play.

### In-game controls

- `Mouse`: select and move pieces when the current side is human-controlled.
- `1` / `2`: cycle White or Black between Human and Minimax on the fly (AI vs AI works too).
- `R`: reset the board (controllers stay as configured).
- `U`: undo the previous move.
- `Esc` or `Q`: quit the session.

The GUI shows which controller is active for each side plus live AI status (“thinking…”, “ready”, etc.). When both sides are AI driven the match progresses automatically; you can still pause by switching a side back to human mid-game. This controller layer is future-proofed for upcoming Monte Carlo tree search, genetic, reinforcement, or remote/server-driven agents so they can challenge one another or a human opponent.
