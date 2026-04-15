from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[2]


def _extract_js_array(source: str, name: str) -> list[str]:
    pattern = rf"const\s+{re.escape(name)}\s*=\s*\[(.*?)\];"
    match = re.search(pattern, source, flags=re.S)
    if not match:
        raise AssertionError(f"Could not find JS array {name}.")
    body = match.group(1)
    return re.findall(r"\"([A-Za-z0-9_]+)\"", body)


def _extract_ai_fields(schemas_py: str) -> set[str]:
    match = re.search(r"class\s+AIConfigFields\(BaseModel\):(.*?)(?:\n\nclass\s+)", schemas_py, flags=re.S)
    if not match:
        raise AssertionError("Could not locate AIConfigFields block.")
    block = match.group(1)
    fields = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*", block, flags=re.M))
    return fields


def _extract_class_block(source: str, class_name: str) -> str:
    pattern = rf"class\s+{re.escape(class_name)}\([^)]*\):(.*?)(?:\n\nclass\s+|\Z)"
    match = re.search(pattern, source, flags=re.S)
    if not match:
        raise AssertionError(f"Could not locate class block for {class_name}.")
    return match.group(1)


def _extract_literal_values(source: str, class_name: str) -> list[str]:
    block = _extract_class_block(source, class_name)
    match = re.search(r"type:\s+(?:Optional\[\s*)?Literal\[(.*?)\]", block, flags=re.S)
    if not match:
        raise AssertionError(f"Could not locate type literal for {class_name}.")
    return re.findall(r"\"([A-Za-z0-9_]+)\"", match.group(1))


class WiringStaticTests(unittest.TestCase):
    def test_frontend_payload_keys_match_backend_schema(self) -> None:
        js_path = REPO_DIR / "frontend" / "src" / "hooks" / "useGameAPI.js"
        schemas_path = REPO_DIR / "backend" / "server" / "schemas.py"

        js = js_path.read_text(encoding="utf-8")
        schemas = schemas_path.read_text(encoding="utf-8")

        minimax_keys = _extract_js_array(js, "MINIMAX_PAYLOAD_KEYS")
        mcts_keys = _extract_js_array(js, "MCTS_PAYLOAD_KEYS")
        fields = _extract_ai_fields(schemas)

        missing = sorted(set(minimax_keys + mcts_keys) - fields)
        self.assertFalse(missing, f"Frontend keys missing from AIConfigFields: {missing}")

    def test_session_ai_move_maps_frontend_keys(self) -> None:
        js_path = REPO_DIR / "frontend" / "src" / "hooks" / "useGameAPI.js"
        session_path = REPO_DIR / "backend" / "server" / "session.py"

        js = js_path.read_text(encoding="utf-8")
        session = session_path.read_text(encoding="utf-8")

        minimax_keys = _extract_js_array(js, "MINIMAX_PAYLOAD_KEYS")
        mcts_keys = _extract_js_array(js, "MCTS_PAYLOAD_KEYS")

        missing = []
        for key in minimax_keys + mcts_keys:
            if f"payload.{key}" not in session:
                missing.append(key)
        self.assertFalse(missing, f"Session.run_ai_move does not reference payload fields: {missing}")

    def test_public_player_types_are_narrowed(self) -> None:
        schemas_path = REPO_DIR / "backend" / "server" / "schemas.py"
        schemas = schemas_path.read_text(encoding="utf-8")

        self.assertEqual(_extract_literal_values(schemas, "PlayerConfigPayload"), ["human", "minimax", "mcts"])
        self.assertEqual(_extract_literal_values(schemas, "EvaluationPlayerConfigPayload"), ["minimax", "mcts"])

    def test_evaluation_request_uses_ai_only_model_and_no_reset_flag(self) -> None:
        schemas_path = REPO_DIR / "backend" / "server" / "schemas.py"
        schemas = schemas_path.read_text(encoding="utf-8")
        evaluation_block = _extract_class_block(schemas, "EvaluationStartRequest")

        self.assertIn("white: EvaluationPlayerConfigPayload", evaluation_block)
        self.assertIn("black: EvaluationPlayerConfigPayload", evaluation_block)
        self.assertNotIn("resetConfigsAfterRun", evaluation_block)


if __name__ == "__main__":
    unittest.main()
