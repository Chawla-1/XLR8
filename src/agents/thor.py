"""
Thor Agent — Prosecutor for Maximum Exposure.

Builds structured claims arguing that trade disruption exposure is SEVERE.
Uses worst-case calculator outputs, no substitution credit.
"""

from __future__ import annotations

from typing import Any

from src.brain.base import BaseBrain
from src.core.trace import TraceLogger


class ThorAgent:
    """
    Thor: builds HIGH exposure claims from calculator data.
    """

    def __init__(self, brain: BaseBrain, trace: TraceLogger):
        self.brain = brain
        self.trace = trace

    def build_claims(
        self,
        case: Any,
        supporting_docs: list[dict] | None = None,
        run_num: int = 1,
    ) -> list[dict]:
        """
        Generate claims for all affected trade routes.
        """
        result = self.brain.decide(
            role="thor",
            task="thor_build_claims",
            context={
                "exposures": case.exposures,
                "supporting_docs": supporting_docs or [],
            },
        )

        claims = result.get("claims", [])

        self.trace.log("claim", "thor", "build_claims", {
            "total_claims": len(claims),
            "routes": [c.get("cell", c.get("route", "")) for c in claims],
        }, round_num=run_num)

        return claims

    def challenge(
        self,
        loki_claims: list[dict],
        doc_tiers: dict[str, int] | None = None,
        round_num: int = 1,
    ) -> list[dict]:
        """
        Challenge Loki's LIMITED exposure claims.
        """
        result = self.brain.decide(
            role="thor",
            task="thor_challenge",
            context={
                "loki_claims": loki_claims,
                "doc_tiers": doc_tiers or {},
            },
        )

        challenges = result.get("challenges", [])

        self.trace.log("challenge", "thor", "challenge_loki", {
            "challenges_issued": len(challenges),
            "targets": [c["target_claim_id"] for c in challenges],
        }, round_num=round_num)

        return challenges

    def defend(
        self,
        challenge: dict,
        original_claim: dict,
        round_num: int = 1,
    ) -> dict:
        """
        Defend or concede a challenged claim.
        """
        result = self.brain.decide(
            role="thor",
            task="thor_defend",
            context={
                "challenge": challenge,
                "original_claim": original_claim,
            },
        )

        self.trace.log("defend", "thor", result.get("action", "defend"), {
            "claim_id": original_claim.get("claim_id"),
            "action": result.get("action"),
        }, round_num=round_num)

        return result
