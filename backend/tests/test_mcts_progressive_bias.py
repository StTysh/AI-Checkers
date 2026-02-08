from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai.mcts import MCTSNode  # noqa: E402
from core.move import Move  # noqa: E402


class ProgressiveBiasTests(unittest.TestCase):
    def test_best_child_prefers_bias_when_otherwise_equal(self) -> None:
        root = MCTSNode()
        move_a = Move(start=(2, 1), steps=((3, 2),))
        move_b = Move(start=(2, 3), steps=((3, 4),))

        a = MCTSNode(parent=root, move=move_a, visits=10, value=0.0, bias=1.0)
        b = MCTSNode(parent=root, move=move_b, visits=10, value=0.0, bias=0.0)
        root.children = [a, b]

        picked = root.best_child(
            exploration_constant=1.4,
            progressive_bias=True,
            pb_weight=1.0,
        )
        self.assertIs(picked, a)


if __name__ == "__main__":
    unittest.main()

