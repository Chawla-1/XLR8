"""
Loki Agent — Defense Counsel for Limited Exposure.

Builds structured claims arguing that trade disruption is MANAGEABLE.
Credits rerouting, price cushion, and partial recovery.
"""

from __future__ import annotations

from typing import Any

from src.brain.base import BaseBrain
from src.core.trace import TraceLogger


class LokiAgent:
    """
    Loki: builds LIMITED exposure claims with mitigation arguments.
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
        Generate claims for all affected trade routes with mitigation.
        """
        # Identify alternative routes (Vanir → X where Orvan → X exists)
        alt_routes = {}
        for route_key, exp in case.exposures.items():
            if "Vanir" in route_key:
                alt_routes[route_key] = exp

        result = self.brain.decide(
            role="loki",
            task="loki_build_claims",
            context={
                "exposures": case.exposures,
                "alternative_routes": alt_routes,
                "supporting_docs": supporting_docs or [],
            },
        )

        claims = result.get("claims", [])

        self.trace.log("claim", "loki", "build_claims", {
            "total_claims": len(claims),
            "routes": [c.get("cell", c.get("route", "")) for c in claims],
        }, round_num=run_num)

        return claims

    def challenge(
        self,
        thor_claims: list[dict],
        doc_tiers: dict[str, int] | None = None,
        round_num: int = 1,
    ) -> list[dict]:
        """
        Challenge Thor's HIGH exposure claims.
        """
        result = self.brain.decide(
            role="loki",
            task="loki_challenge",
            context={
                "thor_claims": thor_claims,
                "doc_tiers": doc_tiers or {},
            },
        )

        challenges = result.get("challenges", [])

        self.trace.log("challenge", "loki", "challenge_thor", {
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
            role="loki",
            task="loki_defend",
            context={
                "challenge": challenge,
                "original_claim": original_claim,
            },
        )

        self.trace.log("defend", "loki", result.get("action", "defend"), {
            "claim_id": original_claim.get("claim_id"),
            "action": result.get("action"),
        }, round_num=round_num)

        return result
