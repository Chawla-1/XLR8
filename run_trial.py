"""
CLI Runner for the Trial of the Nine Realms.
Run this script from the terminal to test the entire pipeline end-to-end:
    python run_trial.py
or with a custom question:
    python run_trial.py "Assess trade exposure for Tolan wheat following the Orvan corridor closure."
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Force UTF-8 on Windows
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.trial.loop import TrialRunner


def main():
    default_q = "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low and high range for wheat and maize imports."
    question = sys.argv[1] if len(sys.argv) > 1 else default_q
    pack_dir = "03_Ragnarok Trial of the Nine Realms/dev_pack_E5"

    print("=" * 70)
    print("🏛️  RAGNAROK: TRIAL OF THE NINE REALMS — PIPELINE RUN")
    print("=" * 70)
    print(f"Question : {question}")
    print(f"Data Pack: {pack_dir}")
    print("-" * 70)

    t0 = time.time()
    runner = TrialRunner(pack_dir=pack_dir)
    print(f"Brain Engine: {type(runner.brain).__name__}")
    print("Running trial through state machine (Heimdall → Thor + Loki → Odin)...")
    
    result = runner.run_trial(question)
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print(f"✅ TRIAL COMPLETED IN {elapsed:.2f}s!")
    print("=" * 70)
    print(f"Saved artifacts in: {runner.output_dir}/")
    print(f"  • Briefing       : {runner.output_dir / 'briefing.md'}")
    print(f"  • Case File      : {runner.output_dir / 'case_file.json'}")
    print(f"  • Run Telemetry  : {runner.output_dir / 'run_01.json'}")
    print(f"  • Trace Audit Log: {runner.output_dir / 'trace.jsonl'}")

    print("\n" + "─" * 70)
    print("📜 EXECUTIVE BRIEFING PREVIEW:")
    print("─" * 70)
    print(result["briefing"])
    print("=" * 70)


if __name__ == "__main__":
    main()
