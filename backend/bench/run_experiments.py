from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import re
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from server.schemas import EvaluationStartRequest, EvaluationStopRequest  # noqa: E402
from server.session import GameSession  # noqa: E402


DEFAULT_GAMES_FOR_TIME_BUDGET = 100_000
DEFAULT_POLL_SECONDS = 2.0


def _log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "experiment"


def _normalize_duration_fields(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    seconds = normalized.get("maxDurationSeconds")
    hours = normalized.pop("maxDurationHours", None)
    minutes = normalized.pop("maxDurationMinutes", None)
    if seconds is None and hours is not None:
        seconds = int(round(float(hours) * 3600))
    if seconds is None and minutes is not None:
        seconds = int(round(float(minutes) * 60))
    if seconds is not None:
        normalized["maxDurationSeconds"] = max(1, int(seconds))
        normalized.setdefault("games", DEFAULT_GAMES_FOR_TIME_BUDGET)
    return normalized


def build_request_payload(defaults: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    payload = _deep_merge(defaults, experiment)
    name = payload.pop("name", None)
    if name and not payload.get("experimentName"):
        payload["experimentName"] = name
    return _normalize_duration_fields(payload)


def build_request(defaults: dict[str, Any], experiment: dict[str, Any], overall_deadline_epoch: float | None) -> EvaluationStartRequest | None:
    payload = build_request_payload(defaults, experiment)
    if overall_deadline_epoch is not None:
        remaining = int(overall_deadline_epoch - time.time())
        if remaining <= 0:
            return None
        current_cap = payload.get("maxDurationSeconds")
        payload["maxDurationSeconds"] = remaining if current_cap is None else min(current_cap, remaining)
    return EvaluationStartRequest.model_validate(payload)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def _format_player(player: dict[str, Any]) -> str:
    algorithm = player.get("type", "unknown")
    if algorithm == "minimax":
        flags = []
        if player.get("alphaBeta"):
            flags.append("ab")
        if player.get("transposition"):
            flags.append("tt")
        if player.get("moveOrdering"):
            flags.append("ord")
        if player.get("quiescence"):
            flags.append("q")
        if player.get("iterativeDeepening"):
            flags.append("id")
        if player.get("historyHeuristic"):
            flags.append("hist")
        if player.get("lmr"):
            flags.append("lmr")
        extras = ",".join(flags) if flags else "plain"
        return (
            f"minimax(depth={player.get('depth')},timeMs={player.get('timeLimitMs')},"
            f"features={extras})"
        )
    if algorithm == "mcts":
        flags = []
        if player.get("mctsTransposition"):
            flags.append("tt")
        if player.get("progressiveWidening"):
            flags.append("pw")
        if player.get("progressiveBias"):
            flags.append("pb")
        extras = ",".join(flags) if flags else "plain"
        return (
            f"mcts(iter={player.get('iterations')},rollout={player.get('rolloutDepth')},"
            f"policy={player.get('rolloutPolicy')},leaf={player.get('leafEvaluation')},"
            f"features={extras})"
        )
    return algorithm


def _format_request_summary(payload: dict[str, Any]) -> str:
    max_duration = payload.get("maxDurationSeconds")
    duration_label = f"{max_duration}s" if max_duration is not None else "-"
    return (
        f"variant={payload.get('variant')}, games={payload.get('games')}, moveCap={payload.get('moveCap')}, "
        f"durationCap={duration_label}, white={_format_player(payload['white'])}, "
        f"black={_format_player(payload['black'])}"
    )


def run_manifest(manifest_path: Path, output_dir: Path, poll_seconds: float, overall_hours: float | None) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    defaults = manifest.get("defaults", {})
    experiments = manifest.get("experiments", [])
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("Manifest must define a non-empty 'experiments' list.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "manifest.resolved.json", manifest)

    overall_deadline_epoch = None
    if overall_hours is not None:
        overall_deadline_epoch = time.time() + max(1.0, overall_hours * 3600.0)
        _log(
            f"Overall wall-clock budget enabled: {overall_hours:.2f}h "
            f"(deadline in {max(0, int(overall_deadline_epoch - time.time()))}s)"
        )

    summary_rows: list[dict[str, Any]] = []
    run_index = 0
    cycle = 0

    while True:
        cycle += 1
        _log(f"Starting manifest cycle {cycle}")
        progressed = False
        for experiment in experiments:
            request = build_request(defaults, experiment, overall_deadline_epoch)
            if request is None:
                _log("Overall time budget exhausted before starting the next experiment.")
                break

            progressed = True
            run_index += 1
            session = GameSession()
            request_payload = request.model_dump()
            experiment_name = request_payload.get("experimentName") or experiment.get("name") or f"experiment-{run_index}"
            run_dir = output_dir / f"{run_index:03d}_{_slugify(experiment_name)}"
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_json(run_dir / "request.json", request_payload)

            _log(f"[run {run_index}] starting: {experiment_name}")
            _log(f"[run {run_index}] request: {_format_request_summary(request_payload)}")
            status = session.start_evaluation(request)
            evaluation_id = status["evaluationId"]
            last_completed = status["completedGames"]
            last_progress_at = time.time()

            try:
                while status["running"]:
                    completed = status["completedGames"]
                    total = status["totalGames"]
                    elapsed = status.get("elapsedWallTimeSeconds")
                    if completed > last_completed:
                        games_delta = completed - last_completed
                        span = max(0.001, time.time() - last_progress_at)
                        rate = games_delta / span
                        _log(
                            f"[run {run_index}] progress {completed}/{total} games, "
                            f"elapsed={elapsed:.1f}s, rate={rate:.2f} games/s"
                        )
                        last_completed = completed
                        last_progress_at = time.time()
                    else:
                        idle_for = time.time() - last_progress_at
                        _log(
                            f"[run {run_index}] heartbeat {completed}/{total} games, "
                            f"elapsed={elapsed:.1f}s, idleFor={idle_for:.1f}s, "
                            f"stop={status.get('stopReason') or '-'}"
                        )
                    time.sleep(max(0.1, poll_seconds))
                    status = session.get_evaluation_status(evaluation_id)
            except KeyboardInterrupt:
                _log(f"[run {run_index}] interruption received, stopping evaluation.")
                status = session.stop_evaluation(EvaluationStopRequest(evaluationId=evaluation_id))
                raise
            finally:
                _write_json(run_dir / "status.json", status)
                _, json_payload = session.get_evaluation_results(evaluation_id, "json")
                _write_json(run_dir / "results.json", json_payload)
                _, csv_payload = session.get_evaluation_results(evaluation_id, "csv")
                _write_text(run_dir / "results.csv", csv_payload)

            summary_rows.append(
                {
                    "runIndex": run_index,
                    "cycle": cycle,
                    "experimentName": experiment_name,
                    "evaluationId": evaluation_id,
                    "completedGames": status["completedGames"],
                    "totalGames": status["totalGames"],
                    "stopReason": status.get("stopReason"),
                    "elapsedWallTimeSeconds": status.get("elapsedWallTimeSeconds"),
                    "whiteWins": status["score"]["whiteWins"],
                    "blackWins": status["score"]["blackWins"],
                    "draws": status["score"]["draws"],
                    "winRateWhite": status["summary"]["winRateWhite"],
                    "winRateBlack": status["summary"]["winRateBlack"],
                    "outputDir": str(run_dir),
                }
            )
            _log(
                f"[run {run_index}] finished: {experiment_name} "
                f"({status.get('stopReason')}, {status['completedGames']} games)"
            )

            if overall_deadline_epoch is not None and time.time() >= overall_deadline_epoch:
                _log("Overall time budget reached after the completed run.")
                break

        if overall_deadline_epoch is None:
            break
        if not progressed or time.time() >= overall_deadline_epoch:
            break

    summary_path = output_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "runIndex",
            "cycle",
            "experimentName",
            "evaluationId",
            "completedGames",
            "totalGames",
            "stopReason",
            "elapsedWallTimeSeconds",
            "whiteWins",
            "blackWins",
            "draws",
            "winRateWhite",
            "winRateBlack",
            "outputDir",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    _log(f"Wrote {len(summary_rows)} completed run summaries to {summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unattended checkers evaluation batches from a manifest.")
    parser.add_argument("--manifest", required=True, help="Path to a JSON manifest.")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[2] / "output" / "evaluation_runs"),
        help="Directory for per-run exports and the aggregate summary.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help="Polling interval used while waiting for each evaluation to finish.",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Repeat the manifest sequence until this overall wall-clock budget is exhausted.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    return run_manifest(
        manifest_path=manifest_path,
        output_dir=output_dir,
        poll_seconds=args.poll_seconds,
        overall_hours=args.hours,
    )


if __name__ == "__main__":
    raise SystemExit(main())
