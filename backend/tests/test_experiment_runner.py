from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from bench import run_experiments  # noqa: E402


class ExperimentRunnerTests(unittest.TestCase):
    def test_build_request_payload_merges_defaults_and_name(self) -> None:
        payload = run_experiments.build_request_payload(
            {
                "variant": "british",
                "games": 200,
                "white": {"type": "minimax", "depth": 4},
            },
            {
                "name": "Depth 6 Match",
                "white": {"depth": 6},
                "black": {"type": "mcts", "iterations": 1000},
            },
        )

        self.assertEqual(payload["experimentName"], "Depth 6 Match")
        self.assertEqual(payload["variant"], "british")
        self.assertEqual(payload["games"], 200)
        self.assertEqual(payload["white"]["type"], "minimax")
        self.assertEqual(payload["white"]["depth"], 6)
        self.assertEqual(payload["black"]["iterations"], 1000)

    def test_build_request_payload_converts_hours_and_injects_large_game_count(self) -> None:
        payload = run_experiments.build_request_payload(
            {"variant": "british"},
            {
                "maxDurationHours": 0.5,
                "white": {"type": "minimax", "depth": 2},
                "black": {"type": "mcts", "iterations": 10},
            },
        )

        self.assertEqual(payload["maxDurationSeconds"], 1800)
        self.assertEqual(payload["games"], run_experiments.DEFAULT_GAMES_FOR_TIME_BUDGET)

    def test_build_request_returns_none_when_overall_deadline_has_expired(self) -> None:
        request = run_experiments.build_request(
            {"variant": "british"},
            {
                "white": {"type": "minimax", "depth": 2},
                "black": {"type": "mcts", "iterations": 10},
            },
            overall_deadline_epoch=0.0,
        )

        self.assertIsNone(request)

    def test_run_manifest_accepts_utf8_bom_and_writes_outputs(self) -> None:
        class FakeSession:
            def __init__(self):
                self._status = None
                self._evaluation_id = None

            def start_evaluation(self, request):
                self._evaluation_id = "eval-1"
                self._status = {
                    "evaluationId": "eval-1",
                    "running": False,
                    "completedGames": 1,
                    "totalGames": request.games,
                    "elapsedWallTimeSeconds": 0.1,
                    "stopReason": "completed_games",
                    "score": {"whiteWins": 1, "blackWins": 0, "draws": 0},
                    "summary": {"winRateWhite": 1.0, "winRateBlack": 0.0},
                }
                return self._status

            def get_evaluation_status(self, evaluation_id):
                return self._status

            def get_evaluation_results(self, evaluation_id, format):
                if format == "json":
                    return "application/json", {"evaluationId": evaluation_id, "running": False}
                return "text/csv", "summary,test\n"

        manifest_text = """{
  "defaults": {"variant": "british", "games": 1},
  "experiments": [
    {
      "name": "bom-manifest",
      "white": {"type": "minimax", "depth": 2},
      "black": {"type": "mcts", "iterations": 10}
    }
  ]
}"""

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(run_experiments, "GameSession", FakeSession):
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(manifest_text, encoding="utf-8-sig")
            output_dir = Path(temp_dir) / "out"

            rc = run_experiments.run_manifest(manifest_path, output_dir, poll_seconds=0.01, overall_hours=None)

            self.assertEqual(rc, 0)
            self.assertTrue((output_dir / "summary.csv").exists())
            self.assertTrue((output_dir / "001_bom-manifest" / "request.json").exists())
            self.assertTrue((output_dir / "001_bom-manifest" / "results.json").exists())
            self.assertTrue((output_dir / "001_bom-manifest" / "results.csv").exists())


if __name__ == "__main__":
    unittest.main()
