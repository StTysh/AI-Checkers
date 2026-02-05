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


if __name__ == "__main__":
    unittest.main()
