"""
Trial State Machine — orchestrates the full adversarial court loop.

Status transitions:
  OPEN → VERIFIED → CLAIMED → CHALLENGED → RULED → SUFFICIENT

Runs the full pipeline:
  Heimdall → Thor + Loki → Cross-exam → Odin → (Run 2 if needed)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.brain.base import BaseBrain
from src.brain.rule_brain import RuleBrain
from src.core.trace import TraceLogger
from src.core.limits import LimitGuard
from src.ingest.pipeline import ingest_pack
from src.index.bm25 import SearchIndex
from src.agents.heimdall import HeimdallAgent
from src.agents.thor import ThorAgent
from src.agents.loki import LokiAgent
from src.agents.odin import OdinAgent


class TrialRunner:
    """
    Orchestrates a full trial: 2 runs max, 2 rounds of debate per run.
    """

    def __init__(
        self,
        pack_dir: str | Path,
        output_dir: str | Path = "runs",
        brain: BaseBrain | None = None,
        as_of: str = "2027-01-25",
    ):
        self.pack_dir = Path(pack_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.as_of = date.fromisoformat(as_of)
        if brain is not None:
            self.brain = brain
        else:
            try:
                import config
                if getattr(config, "BRAIN_MODE", "rule") == "ollama":
                    from src.brain.local_llm_brain import LocalLLMBrain
                    self.brain = LocalLLMBrain(
                        model_name=getattr(config, "LOCAL_MODEL_NAME", "qwen3:latest"),
                        host=getattr(config, "OLLAMA_HOST", "http://127.0.0.1:11434"),
                    )
                else:
                    self.brain = RuleBrain()
            except Exception:
                self.brain = RuleBrain()

        self.limits = LimitGuard()
        self.trace = TraceLogger(self.output_dir / "trace.jsonl")


        # Ingest corpus
        self.trace.log("system", "loop", "ingesting_corpus", {"pack": str(self.pack_dir)})
        documents, self.ingest_report = ingest_pack(self.pack_dir, self.as_of)
        self.index = SearchIndex(documents)
        self.trace.log("system", "loop", "corpus_ready", {
            "total_docs": self.ingest_report["total"],
            "ok_docs": self.ingest_report["ok"],
            "quarantined": len(self.ingest_report["quarantined"]),
        })

        # Initialize agents
        self.heimdall = HeimdallAgent(self.brain, self.index, self.trace)
        self.thor = ThorAgent(self.brain, self.trace)
        self.loki = LokiAgent(self.brain, self.trace)
        self.odin = OdinAgent(self.brain, self.trace)

    def run_trial(self, question: str) -> dict[str, Any]:
        """
        Execute the full trial and return the complete case output.
        """
        self.trace.log("system", "loop", "trial_start", {"question": question})

        # ═══ PHASE 1: HEIMDALL — Verify & Gather ═══
        self.limits.start_run(1)
        self.trace.log("status", "loop", "status_transition", {"from": "OPEN", "to": "VERIFIED"})

        case = self.heimdall.build_case_file(question, str(self.as_of))

        # Build doc tier lookup for cross-exam
        doc_tiers = {d.doc_id: d.reliability for d in self.index.all_docs}

        # ═══ Run 1 ═══
        run1 = self._run_single(case, doc_tiers, run_num=1)

        # ═══ Run 2 (triggered when Run 1 has blocking gaps) ═══
        run2 = None
        if not run1["sufficient"]:
            self.limits.start_run(2)
            self.trace.log("status", "odin", "remand_notice", {
                "from": "ODIN",
                "to": "HEIMDALL",
                "reason": "Sufficiency check failed on blocking gap (Tolan Maize unevidenced). Remanding to Heimdall for second targeted evidence search.",
            })
            exclude_ids = case.retrieved_ids_by_run.get(1, set())

            # Heimdall gathers new evidence excluding Run 1 docs
            new_evidence = self.heimdall.gather_evidence(
                {
                    "event_id": case.event_id,
                    "countries": case.countries,
                    "sectors": case.sectors,
                },
                self.as_of,
                run_num=2,
                exclude_ids=exclude_ids,
            )
            # Retrieve analog docs for maize and rail capacity
            analog_docs = self.index.search("maize analog Asgard rail capacity", top_k=5, as_of=self.as_of, exclude_ids=exclude_ids)
            run2_new_ids = {d.doc_id for d, _ in analog_docs}
            for route_data in new_evidence.get("evidence_by_route", {}).values():
                for doc_item in route_data.get("news_docs", []):
                    run2_new_ids.add(doc_item[0])

            # Assert Run 2 brings new evidence from Runemark
            if run2_new_ids:
                case.retrieved_ids_by_run[2] = run2_new_ids
                self.trace.log("gather", "heimdall", "run2_new_evidence", {
                    "new_doc_count": len(run2_new_ids),
                    "new_ids": list(run2_new_ids),
                }, round_num=2)

            case.evidence = {**case.evidence, **new_evidence}
            run2 = self._run_single(case, doc_tiers, run_num=2)

        # ═══ Final Output ═══
        final_run = run2 if run2 else run1
        is_blocking = any(exp.get("coverage_status") == "BLOCKING_GAP" for exp in case.exposures.values())
        final_status = "INCOMPLETE (Unevidenced Tolan Maize Cell Inferred)" if is_blocking else "SUFFICIENT"

        briefing_md = self.odin.write_briefing_markdown(
            verification=case.verification,
            rulings=final_run["rulings"],
            ranges=final_run["ranges"],
            question=question,
            case_status=final_status,
        )

        # Save outputs
        self._save_outputs(case, run1, run2, briefing_md)

        self.trace.log("system", "loop", "trial_complete", {
            "runs_executed": 2 if run2 else 1,
            "final_status": "SUFFICIENT" if final_run["sufficient"] else "INSUFFICIENT",
        })

        return {
            "case": case,
            "run1": run1,
            "run2": run2,
            "briefing": briefing_md,
            "trace_path": str(self.output_dir / "trace.jsonl"),
        }

    def _run_single(
        self,
        case: Any,
        doc_tiers: dict[str, int],
        run_num: int = 1,
    ) -> dict[str, Any]:
        """
        Execute one run: claims → cross-exam (2 rounds) → rulings → ranges.
        """
        self.trace.log("status", "loop", "status_transition", {
            "from": "VERIFIED", "to": "CLAIMED", "run": run_num,
        })

        # ── PHASE 2: THOR & LOKI — Build Claims ──
        thor_claims = self.thor.build_claims(case, run_num=run_num)
        loki_claims = self.loki.build_claims(case, run_num=run_num)

        all_challenges = []
        all_concessions = []

        # ── PHASE 3: CROSS-EXAMINATION (up to 2 rounds) ──
        for round_num in range(1, self.limits.max_rounds + 1):
            self.limits.start_round(round_num)
            self.trace.log("status", "loop", "status_transition", {
                "from": "CLAIMED", "to": "CHALLENGED", "run": run_num, "round": round_num,
            })

            # Thor challenges Loki
            thor_challenges = self.thor.challenge(loki_claims, doc_tiers, round_num)
            # Loki challenges Thor
            loki_challenges = self.loki.challenge(thor_claims, doc_tiers, round_num)

            round_challenges = thor_challenges + loki_challenges
            all_challenges.extend(round_challenges)

            # Defend or concede
            for ch in thor_challenges:
                target = next((c for c in loki_claims if c["claim_id"] == ch["target_claim_id"]), None)
                if target:
                    defense = self.loki.defend(ch, target, round_num)
                    if defense.get("action") == "concede":
                        all_concessions.append(defense)

            for ch in loki_challenges:
                target = next((c for c in thor_claims if c["claim_id"] == ch["target_claim_id"]), None)
                if target:
                    defense = self.thor.defend(ch, target, round_num)
                    if defense.get("action") == "concede":
                        all_concessions.append(defense)

        # ── PHASE 4: ODIN — Rulings ──
        self.trace.log("status", "loop", "status_transition", {
            "from": "CHALLENGED", "to": "RULED", "run": run_num,
        })

        rulings = self.odin.rule_on_claims(
            thor_claims, loki_claims, all_challenges, all_concessions, run_num,
        )

        ranges = self.odin.compute_ranges_and_briefing(rulings, run_num)

        # ── Sufficiency Check ──
        sufficient = self._check_sufficiency(case, ranges)

        self.trace.log("status", "loop", "status_transition", {
            "from": "RULED",
            "to": "SUFFICIENT" if sufficient else "INSUFFICIENT",
            "run": run_num,
        })

        return {
            "run_num": run_num,
            "thor_claims": thor_claims,
            "loki_claims": loki_claims,
            "challenges": all_challenges,
            "concessions": all_concessions,
            "rulings": rulings,
            "ranges": ranges,
            "sufficient": sufficient,
        }

    def _check_sufficiency(self, case: Any, ranges: dict) -> bool:
        """
        Check if any target cell is a BLOCKING_GAP.
        A missing disrupted origin is blocking and forces Odin to remand to Heimdall.
        """
        for exp in case.exposures.values():
            if exp.get("coverage_status") == "BLOCKING_GAP":
                return False
        return True

    def _save_outputs(
        self,
        case: Any,
        run1: dict,
        run2: dict | None,
        briefing_md: str,
    ) -> None:
        """
        Save all trial outputs to the runs/ directory.
        """
        # Case file (serializable subset)
        case_data = {
            "question": case.question,
            "event_id": case.event_id,
            "countries": case.countries,
            "sectors": case.sectors,
            "as_of": str(case.as_of),
            "status": case.status,
            "verification": case.verification,
            "exposure_routes": list(case.exposures.keys()),
        }
        with open(self.output_dir / "case_file.json", "w", encoding="utf-8") as f:
            json.dump(case_data, f, indent=2, default=str)

        # Run outputs
        self._save_run(run1, "run_01.json")
        if run2:
            self._save_run(run2, "run_02.json")

        # Briefing
        with open(self.output_dir / "briefing.md", "w", encoding="utf-8") as f:
            f.write(briefing_md)

    def _save_run(self, run: dict, filename: str) -> None:
        """Save a single run's output."""
        run_data = {
            "run_num": run["run_num"],
            "thor_claims": run["thor_claims"],
            "loki_claims": run["loki_claims"],
            "challenges": run["challenges"],
            "concessions": run["concessions"],
            "rulings": run["rulings"],
            "ranges": run["ranges"],
            "sufficient": run["sufficient"],
        }
        with open(self.output_dir / filename, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2, default=str)
