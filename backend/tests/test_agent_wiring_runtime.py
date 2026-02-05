from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai import minimax  # noqa: E402
from ai.agents import create_mcts_controller, create_minimax_controller  # noqa: E402
from core.game import Game  # noqa: E402


def _closure_vars(func) -> dict[str, object]:
    if func.__closure__ is None:
        return {}
    return dict(zip(func.__code__.co_freevars, [cell.cell_contents for cell in func.__closure__]))


class AgentWiringRuntimeTests(unittest.TestCase):
    def test_minimax_transposition_flag_changes_tt_usage(self) -> None:
        game = Game(board_size=8)

        minimax.clear_transposition_table()
        ctrl_no_tt = create_minimax_controller("T", depth=3, use_transposition=False, use_alpha_beta=True)
        _ = ctrl_no_tt.select_move(game)
        self.assertEqual(len(minimax._TRANSPOSITION_TABLE), 0)

        minimax.clear_transposition_table()
        ctrl_tt = create_minimax_controller("T", depth=3, use_transposition=True, use_alpha_beta=True)
        _ = ctrl_tt.select_move(game)
        self.assertGreater(len(minimax._TRANSPOSITION_TABLE), 0)

    def test_mcts_controller_closure_contains_key_flags(self) -> None:
        ctrl = create_mcts_controller(
            "T",
            iterations=123,
            rollout_depth=45,
            exploration_constant=0.9,
            use_parallel=True,
            workers=3,
            rollout_policy="minimax_guided",
            guidance_depth=2,
            rollout_cutoff_depth=10,
            leaf_evaluation="minimax_eval",
            use_transposition=True,
            transposition_max_entries=9999,
            progressive_widening=True,
            pw_k=1.7,
            pw_alpha=0.6,
        )
        self.assertIsNotNone(ctrl.policy)
        vars_ = _closure_vars(ctrl.policy)
        expected = {
            "iterations": 123,
            "rollout_depth": 45,
            "exploration_constant": 0.9,
            "use_parallel": True,
            "workers": 3,
            "rollout_policy": "minimax_guided",
            "guidance_depth": 2,
            "rollout_cutoff_depth": 10,
            "leaf_evaluation": "minimax_eval",
            "use_transposition": True,
            "transposition_max_entries": 9999,
            "progressive_widening": True,
            "pw_k": 1.7,
            "pw_alpha": 0.6,
        }
        for key, value in expected.items():
            self.assertIn(key, vars_)
            self.assertEqual(vars_[key], value)


if __name__ == "__main__":
    unittest.main()
