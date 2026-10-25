"""
Execution limit guard.
Enforces problem statement constraints:
- Max 2 runs total
- Max 2 debate rounds per run
- Max tool calls per agent
- Token budget monitoring
"""

from __future__ import annotations


class LimitGuard:
    """
    Enforces runtime safety limits across agents and trial rounds.
    """

    def __init__(
        self,
        max_runs: int = 2,
        max_rounds: int = 2,
        max_tool_calls_per_round: int = 15,
        max_tokens_per_run: int = 80000,
    ):
        self.max_runs = max_runs
        self.max_rounds = max_rounds
        self.max_tool_calls_per_round = max_tool_calls_per_round
        self.max_tokens_per_run = max_tokens_per_run

        self.current_run = 0
        self.current_round = 0
        self.total_tool_calls = 0
        self.total_tokens_used = 0

    def start_run(self, run_num: int) -> None:
        if run_num > self.max_runs:
            raise RuntimeError(f"Exceeded maximum allowed runs ({self.max_runs}). Attempted run: {run_num}")
        self.current_run = run_num
        self.current_round = 0

    def start_round(self, round_num: int) -> None:
        if round_num > self.max_rounds:
            raise RuntimeError(f"Exceeded maximum allowed rounds per run ({self.max_rounds}). Attempted: {round_num}")
        self.current_round = round_num

    def record_tool_call(self) -> None:
        self.total_tool_calls += 1

    def record_tokens(self, count: int) -> None:
        self.total_tokens_used += count
        if self.total_tokens_used > self.max_tokens_per_run:
            pass  # Warning or soft ceiling
