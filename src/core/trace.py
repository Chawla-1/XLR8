"""
Execution trace logger.
Logs all agent actions, tool calls, and state transitions to a JSONL file.
Required for post-trial audit and live UI replay.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class TraceLogger:
    """
    Appends structured events to runs/<case_id>/trace.jsonl.
    Thread-safe and append-only.
    """

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        event_type: str,
        agent: str,
        action: str,
        details: dict[str, Any] | None = None,
        round_num: int = 1,
    ) -> dict[str, Any]:
        """
        Record an action in the trace log.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "round": round_num,
            "agent": agent,
            "event_type": event_type,
            "action": action,
            "details": details or {},
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry
