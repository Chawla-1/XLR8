"""
Local LLM Brain — connects to local Ollama instance for free, offline inference.
Supports local models (e.g. Qwen 2.5 / Qwen 3, Llama 3.1) with hardware acceleration.
Includes deterministic fallback to RuleBrain for guaranteed validity and low latency.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from src.brain.base import BaseBrain
from src.brain.rule_brain import RuleBrain


class LocalLLMBrain(BaseBrain):
    """
    Brain implementation using a local LLM via Ollama API.
    Zero API cost, fully private, GPU-accelerated.
    """

    def __init__(
        self,
        model_name: str = "qwen3:latest",
        host: str = "http://127.0.0.1:11434",
        timeout: int = 25,
        fallback_brain: BaseBrain | None = None,
    ):
        self.model_name = model_name
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.fallback = fallback_brain or RuleBrain()

    def decide(
        self,
        role: str,
        task: str,
        context: dict[str, Any],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute reasoning.
        Uses local LLM for narrative/argumentation tasks (Thor, Loki, Odin Briefing).
        Uses deterministic RuleBrain for mechanical/math/indexing tasks.
        """
        # Always compute baseline data first (guarantees mathematical accuracy)
        baseline = self.fallback.decide(role, task, context, system_prompt)

        # 1. Executive Briefing by Odin — High-value LLM synthesis
        if role == "odin" and task == "write_briefing":
            llm_briefing = self._generate_briefing(context, baseline)
            if llm_briefing and len(llm_briefing) > 100:
                return {"briefing_md": llm_briefing}
            return baseline

        # 2. Thor Prosecutorial Claims — Enrich with LLM narrative
        if role == "thor" and task == "build_claims":
            enriched = self._enrich_thor_claims(context, baseline)
            return enriched or baseline

        # 3. Loki Defense Claims — Enrich with LLM mitigation narrative
        if role == "loki" and task == "build_claims":
            enriched = self._enrich_loki_claims(context, baseline)
            return enriched or baseline

        # For all other operational tasks (parsing, checking, cross-exam grounds, rulings),
        # use deterministic logic to ensure sub-second response times and zero format errors.
        return baseline

    def _generate_briefing(self, context: dict[str, Any], fallback_result: dict[str, Any]) -> str | None:
        """Ask local LLM to write a high-level executive briefing markdown."""
        rulings = context.get("rulings", [])
        ranges = context.get("ranges", {})
        question = context.get("question", "")

        prompt = f"""You are Odin, Supreme Magistrate presiding over the Trial of the Nine Realms.
Write an authoritative, professional Executive Briefing in Markdown assessing trade disruption.

Case Question: {question}
Verified Exposure Ranges:
{json.dumps(ranges, indent=2)}

Total Rulings: {len(rulings)} (Established: {sum(1 for r in rulings if getattr(r, 'classification', '') == 'Established')}, Contested: {sum(1 for r in rulings if getattr(r, 'classification', '') == 'Contested')})

Your response MUST follow this exact Markdown structure:
# Executive Briefing — Trial of the Nine Realms
## Executive Summary
(Summarize the event, severity, and key finding in 2-3 sentences)

## Exposure Ranges by Trade Route
| Route | Thor (High) | Loki (Low) | Odin Midpoint | Status |
|---|---|---|---|---|
(Generate table matching the verified exposure ranges)

## Established Facts
(Bullet points of undisputed trade drops)

## Contested Claims
(Bullet points of claims contested on rerouting or price cushions)

## Strategic Outlook & Guidance
(Actionable guidance for decision-makers)
"""
        return self._call_ollama(
            prompt,
            system_prompt="You are Odin, impartial magistrate. Output only Markdown.",
            json_format=False,
            max_tokens=600,
        )

    def _enrich_thor_claims(self, context: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any] | None:
        """Enrich Thor's claims with persuasive prosecutorial reasoning."""
        claims = baseline.get("claims", [])
        if not claims:
            return baseline

        # Keep numbers intact, ask LLM for crisp prosecutorial assumptions
        prompt = f"""You are Thor, Prosecutor demanding maximum preparedness for trade disruption.
For each affected route, provide a sharp 1-sentence risk warning emphasizing supply failure:
Routes: {[c.get('route') for c in claims]}

Return JSON: {{"warnings": ["warning 1", "warning 2", ...]}}"""

        res = self._call_ollama(prompt, system_prompt="You are Thor, harsh prosecutor. Output JSON.", json_format=True, max_tokens=250)
        if res and isinstance(res, dict) and "warnings" in res:
            warnings = res["warnings"]
            for i, c in enumerate(claims):
                if i < len(warnings):
                    c["assumptions"] = [str(warnings[i])]
        return {"claims": claims}

    def _enrich_loki_claims(self, context: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any] | None:
        """Enrich Loki's claims with sharp defense arguments."""
        claims = baseline.get("claims", [])
        if not claims:
            return baseline

        prompt = f"""You are Loki, Defense Counsel arguing disruption is manageable.
For each affected route, provide a sharp 1-sentence mitigation argument citing price resilience or alternative trade:
Routes: {[c.get('route') for c in claims]}

Return JSON: {{"mitigations": ["mitigation 1", "mitigation 2", ...]}}"""

        res = self._call_ollama(prompt, system_prompt="You are Loki, sharp defense counsel. Output JSON.", json_format=True, max_tokens=250)
        if res and isinstance(res, dict) and "mitigations" in res:
            mitigations = res["mitigations"]
            for i, c in enumerate(claims):
                if i < len(mitigations):
                    c["assumptions"] = [str(mitigations[i])]
        return {"claims": claims}

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_format: bool = True,
        max_tokens: int = 500,
    ) -> Any:
        """Call Ollama REST API with timeout and token cap."""
        url = f"{self.host}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.2,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt
        if json_format:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                text = body.get("response", "").strip()
                if json_format:
                    return json.loads(text)
                return text
        except Exception:
            return None
