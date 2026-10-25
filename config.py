"""
Project configuration.
Loads settings from environment or uses sensible defaults.
No API key required for local/rule-based mode.
"""

from __future__ import annotations

import os
from pathlib import Path


# ── Paths ──
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "03_Ragnarok Trial of the Nine Realms" / "dev_pack_E5"
RUNS_DIR = PROJECT_ROOT / "runs"

# ── Local LLM (Ollama) settings ──
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "qwen3:latest")

# ── Trial limits ──
MAX_RUNS = int(os.getenv("MAX_RUNS", "2"))
MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "2"))

# ── Brain mode: "ollama" (local GPU LLM), "rule" (pure deterministic), or "claude" ──
BRAIN_MODE = os.getenv("BRAIN_MODE", "ollama")

# ── Default as-of date for clock filter ──
DEFAULT_AS_OF = "2027-01-25"

