"""
Heimdall Agent — Guardian of Evidence and Temporal Truth.

Responsibilities:
1. Parse the user's question to extract event, countries, sectors, as-of date
2. Verify the event is real using T1/T2 sources + trade table dip
3. Detect retractions (supersession chain)
4. Flag prompt injections and T4 unreliable docs
5. Populate the initial Case File with verified evidence
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.brain.base import BaseBrain
from src.core.schemas import Document, CaseFile, Citation
from src.core.trace import TraceLogger
from src.index.bm25 import SearchIndex
from src.calc.tables import extract_all_trade_tables, group_by_route
from src.calc.baseline import compute_all_requested_exposures


class HeimdallAgent:
    """
    Heimdall: event verification, evidence retrieval, case file builder.
    """

    def __init__(self, brain: BaseBrain, index: SearchIndex, trace: TraceLogger):
        self.brain = brain
        self.index = index
        self.trace = trace

    def parse_question(self, question: str, as_of: str = "2027-01-25") -> dict[str, Any]:
        """
        Extract structured parameters from the user's question.
        """
        result = self.brain.decide(
            role="heimdall",
            task="heimdall_parse_question",
            context={"question": question, "as_of": as_of},
        )
        self.trace.log("parse", "heimdall", "parse_question", result)
        return result

    def verify_event(
        self,
        event_id: str,
        as_of: date,
        run_num: int = 1,
        exclude_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Verify the event is real:
        - Search for T1/T2 docs about the event
        - Check for trade data dip
        - Detect retractions
        - Flag T4/injections
        """
        # 1. Search for event-related documents
        event_docs = self.index.search(
            query=f"event {event_id} corridor disruption",
            top_k=20,
            event_id=event_id,
            as_of=as_of,
            exclude_ids=exclude_ids,
        )

        # 2. Categorize by tier
        t1_docs = []
        t2_docs = []
        t4_docs = []
        all_evidence = []

        for doc, score in event_docs:
            entry = {
                "doc_id": doc.doc_id,
                "tier": doc.reliability,
                "title": doc.title,
                "score": round(score, 2),
                "source": doc.source_type,
            }
            all_evidence.append(entry)

            if doc.reliability == 1:
                t1_docs.append(entry)
            elif doc.reliability == 2:
                t2_docs.append(entry)
            elif doc.reliability >= 4:
                t4_docs.append(entry)

        # 3. Check for retractions (supersession)
        retractions = self._find_retractions(event_id, as_of)

        # 4. Detect trade data dip
        trade_dip = self._check_trade_dip(as_of)

        # 5. Detect prompt injections
        traps = self._scan_injections()

        # 6. Ask brain to verify
        verification = self.brain.decide(
            role="heimdall",
            task="heimdall_verify_event",
            context={
                "evidence": all_evidence,
                "trade_dip_detected": trade_dip,
                "retractions": retractions,
            },
        )

        result = {
            **verification,
            "event_id": event_id,
            "evidence_docs": all_evidence,
            "retractions": retractions,
            "traps_caught": traps,
            "retrieved_ids": [e["doc_id"] for e in all_evidence],
        }

        self.trace.log("verify", "heimdall", "verify_event", {
            "event_id": event_id,
            "verified": verification["verified"],
            "confidence": verification["confidence"],
            "t1_count": len(t1_docs),
            "t2_count": len(t2_docs),
            "t4_flagged": len(t4_docs),
            "traps_caught": len(traps),
        }, round_num=run_num)

        return result

    def gather_evidence(
        self,
        parsed: dict,
        as_of: date,
        run_num: int = 1,
        exclude_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve all evidence for the case file:
        - Event docs (news, analysis)
        - Trade notes per country/sector
        - Background (atlas) docs
        """
        event_id = parsed["event_id"]
        countries = parsed["countries"]
        sectors = parsed["sectors"]

        all_retrieved = {}

        # Per-country, per-sector evidence
        for country in countries:
            for sector in sectors:
                # News/analysis docs
                news = self.index.search(
                    query=f"{country} {sector} trade disruption exposure",
                    top_k=8,
                    event_id=event_id,
                    country=country,
                    as_of=as_of,
                    exclude_ids=exclude_ids,
                )

                # Trade notes
                trade_notes = self.index.filter_docs(
                    event_id=event_id,
                    country=country,
                    source_type="trade note",
                    as_of=as_of,
                )

                key = f"{country} ({sector})"
                all_retrieved[key] = {
                    "news_docs": [(d.doc_id, d.title, round(s, 2)) for d, s in news],
                    "trade_notes": [d.doc_id for d in trade_notes],
                }

        # Background/atlas docs (no event filter)
        atlas_docs = self.index.filter_docs(
            source_type="atlas",
            as_of=as_of,
        )

        self.trace.log("gather", "heimdall", "gather_evidence", {
            "countries": countries,
            "sectors": sectors,
            "route_count": len(all_retrieved),
        }, round_num=run_num)

        return {
            "evidence_by_route": all_retrieved,
            "atlas_docs": [d.doc_id for d in atlas_docs],
        }

    def build_case_file(
        self,
        question: str,
        as_of_str: str = "2027-01-25",
    ) -> CaseFile:
        """
        Full Heimdall pipeline: parse → verify → gather → build CaseFile.
        """
        as_of = date.fromisoformat(as_of_str)

        # Step 1: Parse the question
        parsed = self.parse_question(question, as_of_str)

        # Step 2: Verify the event
        verification = self.verify_event(parsed["event_id"], as_of)

        if not verification["verified"]:
            self.trace.log("warn", "heimdall", "event_not_verified", {
                "event_id": parsed["event_id"],
                "confidence": verification["confidence"],
            })

        # Step 3: Gather evidence
        evidence = self.gather_evidence(parsed, as_of)

        # Step 4: Extract trade tables and compute importer-level exposures
        trade_rows = extract_all_trade_tables(self.index.active_docs)
        trade_tables = group_by_route(trade_rows)
        exposures = compute_all_requested_exposures(parsed["countries"], parsed["sectors"], trade_rows)

        # Step 5: Build the CaseFile
        case = CaseFile(
            question=question,
            event_id=parsed["event_id"],
            countries=parsed["countries"],
            sectors=parsed["sectors"],
            as_of=as_of,
            status="VERIFIED" if verification["verified"] else "OPEN",
        )
        case.verification = verification
        case.evidence = evidence
        case.exposures = exposures
        case.trade_tables = trade_tables
        
        # Track Run 1 retrieved IDs
        run1_ids = set(verification.get("retrieved_ids", []))
        for route_data in evidence.get("evidence_by_route", {}).values():
            for doc_item in route_data.get("news_docs", []):
                run1_ids.add(doc_item[0])
            for tid in route_data.get("trade_notes", []):
                run1_ids.add(tid)
        case.retrieved_ids_by_run = {1: run1_ids}

        self.trace.log("build", "heimdall", "case_file_created", {
            "event_id": case.event_id,
            "status": case.status,
            "countries": case.countries,
            "sectors": case.sectors,
            "exposure_routes": list(exposures.keys()),
        })

        return case

    # ── Private helpers ──

    def _find_retractions(self, event_id: str, as_of: date) -> list[dict]:
        """
        Search for retraction/correction documents.
        """
        retraction_docs = self.index.search(
            query="correction retraction supersedes replaces withdrawn",
            top_k=10,
            event_id=event_id,
            as_of=as_of,
        )

        retractions = []
        for doc, score in retraction_docs:
            text_lower = doc.text.lower()
            if any(w in text_lower for w in ["retract", "correct", "supersed", "replac", "withdrawn"]):
                # Try to find which doc it retracts
                retracted_id = None
                match = re.search(r'(ATL|ORV|WLD)-\d{4}', doc.text)
                if match:
                    retracted_id = match.group(0)
                    if retracted_id != doc.doc_id:
                        retractions.append({
                            "retractor_id": doc.doc_id,
                            "retracted_id": retracted_id,
                            "tier": doc.reliability,
                        })
        return retractions

    def _check_trade_dip(self, as_of: date) -> bool:
        """
        Check if trade data shows a significant dip (>20%) in any route.
        """
        trade_notes = self.index.filter_docs(
            source_type="trade_note",
            as_of=as_of,
        )
        trade_rows = extract_all_trade_tables(trade_notes)
        tables = group_by_route(trade_rows)
        for route_key, rows in tables.items():
            ok_rows = [r for r in rows if r.status == "ok"]
            if len(ok_rows) >= 4:
                val_2026 = [r.value_usd_m for r in ok_rows if r.year == 2026]
                if len(val_2026) >= 4:
                    pre = sum(val_2026[:2]) / 2
                    post = sum(val_2026[2:]) / len(val_2026[2:])
                    if pre > 0 and ((post - pre) / pre) < -0.20:
                        return True
        return False

    def _scan_injections(self) -> list[dict]:
        """
        Scan all indexed docs for prompt injection phrases.
        """
        injection_patterns = [
            r"ignore\s+(your|all|previous)\s+(rules|instructions)",
            r"you\s+are\s+now",
            r"disregard\s+(everything|all)",
            r"system\s*:\s*",
            r"<\s*system\s*>",
        ]

        traps = []
        for doc in self.index.all_docs:
            text = doc.text.lower()
            for pattern in injection_patterns:
                if re.search(pattern, text):
                    traps.append({
                        "doc_id": doc.doc_id,
                        "type": "prompt_injection",
                        "pattern": pattern,
                    })
                    break
        return traps
