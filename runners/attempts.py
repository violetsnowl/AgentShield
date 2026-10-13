"""C-side attempt log. Written before and after every dispatch; B's events cannot replace it."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

_SECRETISH = re.compile(r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]{8,})")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return _SECRETISH.sub("[REDACTED]", value)[:2000]
    if isinstance(value, list):
        return [safe(v, depth + 1) for v in value[:50]]
    if isinstance(value, dict):
        return {str(k)[:128]: safe(v, depth + 1) for k, v in list(value.items())[:50]}
    return value


class AttemptLog:
    def __init__(self, path: Path):
        self.path = path
        self.seq = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError("Attempt log already exists; never append to earlier evidence.")
        path.touch()

    def record(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.seq += 1
        row = {"attempt_seq": self.seq, "recorded_at": now(), "kind": kind, **{k: safe(v) for k, v in fields.items()}}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def rows(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
