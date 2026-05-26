from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


def _safe_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":"))


@dataclass
class AuditLogger:
    path: Path

    def write(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_safe_json(record) + "\n")

    @contextmanager
    def call(self, tool: str, transport: str, **extra: Any) -> Iterator[dict[str, Any]]:
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        started = time.perf_counter()
        record: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id,
            "tool": tool,
            "transport": transport,
            "status": "ok",
        }
        record.update(extra)
        try:
            yield record
        except Exception as exc:
            record["status"] = "error"
            record["error_type"] = type(exc).__name__
            raise
        finally:
            record["duration_ms"] = int((time.perf_counter() - started) * 1000)
            self.write(record)
