"""
Core Pydantic schemas for the Trial of the Nine Realms.
These are the contracts between all modules — freeze before writing agent code.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class DocStatus(str, Enum):
    OK = "ok"
    DAMAGED = "damaged"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    INJECTED = "injected"
    CLOCK_VIOLATION = "clock_violation"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    VERIFIED = "VERIFIED"
    CLAIMED = "CLAIMED"
    CHALLENGED = "CHALLENGED"
    RULED = "RULED"
    SUFFICIENT = "SUFFICIENT"
    RETURNED = "RETURNED"
    INCOMPLETE = "INCOMPLETE"


class ClaimType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"


class RulingClass(str, Enum):
    ESTABLISHED = "Established"
    CONTESTED = "Contested"
    CONCEDED = "Conceded"
    REJECTED = "Rejected"


# ── Document & Trade Data ──────────────────────────────────────────────────

class Document(BaseModel):
    """A parsed document from the corpus."""
    doc_id: str                     # "ORV-0009"
    event_id: str                   # "E5" or "NONE"
    title: str
    source_name: str
    source_type: str                # "trade_note", "gov_notice", "news", etc.
    reliability: int                # 1–4
    pub_date: date
    pub_time: str                   # "09:20"
    country: str
    sector: str
    language: str = "en"
    file_path: str                  # relative path to the file
    file_format: str                # "TXT", "PDF", "DOCX"
    text: str                       # full body text
    paragraphs: dict[str, str]      # {"P1": "...", "P2": "..."}
    sha256: str                     # content hash for dedup
    status: DocStatus = DocStatus.OK
    quarantine_reason: str | None = None


class TradeRow(BaseModel):
    """A single month's trade data extracted from a trade note."""
    table_id: str                   # "ORV-0009" (doc it came from)
    paragraph: str                  # "P2" (paragraph it was extracted from)
    month: str                      # "2026-07"
    year: int
    value_usd_m: float              # 90.0
    volume_kt: float                # 250.0 (in thousands of tonnes)
    commodity: str                  # "wheat" or "maize"
    origin: str                     # "Orvan"
    destination: str                # "Midgard"
    status: Literal["ok", "damaged", "missing"] = "ok"


# ── Citations & Claims ─────────────────────────────────────────────────────

class Citation(BaseModel):
    """A reference to a specific paragraph in a document."""
    doc_id: str                     # "ORV-0009"
    paragraph: str                  # "P2"
    quote: str | None = None        # optional verbatim excerpt


class Claim(BaseModel):
    """A claim made by Thor or Loki about trade exposure."""
    claim_id: str
    side: Literal["thor", "loki"]
    country: str
    sector: str
    low_pct: float                  # low end of exposure range (%)
    high_pct: float                 # high end of exposure range (%)
    metric: Literal["value", "volume"]
    claim_type: ClaimType
    evidence: list[Citation]
    assumptions: list[str] = []
    conceded: bool = False
    concession_reason: str | None = None


class Challenge(BaseModel):
    """A cross-examination challenge against a claim."""
    challenger: Literal["thor", "loki"]
    target_claim_id: str
    grounds: Literal[
        "tier", "retraction", "event_mismatch",
        "number_error", "clock_violation", "contradiction"
    ]
    reasoning: str
    counter_evidence: list[Citation] = []


class Response(BaseModel):
    """Defence or concession in response to a challenge."""
    responder: Literal["thor", "loki"]
    target_claim_id: str
    action: Literal["defend", "concede"]
    new_evidence: list[Citation] | None = None
    reason: str


# ── Rulings ────────────────────────────────────────────────────────────────

class Ruling(BaseModel):
    """Odin's ruling on a single claim."""
    claim_id: str
    kind: ClaimType                 # fact or inference
    classification: RulingClass     # Established / Contested / Conceded / Rejected
    reasons: str
    citations_valid: bool
    odin_low_pct: float | None = None   # Odin's refined range (if applicable)
    odin_high_pct: float | None = None


# ── Event Verification ─────────────────────────────────────────────────────

class EventVerification(BaseModel):
    """Heimdall's verification of whether the event is real."""
    event_id: str
    event_name: str
    is_verified: bool
    confirming_docs: list[Citation]     # T1/T2 sources that confirm
    retractions: list[Citation] = []    # docs that were retracted
    superseded_docs: list[str] = []     # doc_ids that are superseded
    clock_violations: list[str] = []    # doc_ids published after as_of
    tier4_flagged: list[str] = []       # doc_ids flagged as unreliable
    quarantined: list[str] = []         # doc_ids quarantined (empty/damaged/etc.)
    reasoning: str = ""


# ── Case File ──────────────────────────────────────────────────────────────

class CaseFile(BaseModel):
    """The shared blackboard — all agents read and write to this."""
    case_id: str
    question: str
    as_of: date
    event_id: str
    target_flows: list[tuple[str, str]]  # [(country, sector), ...]
    verification: EventVerification | None = None
    status: CaseStatus = CaseStatus.OPEN
    run_no: int = 1
    round_no: int = 1
    claims: list[Claim] = []
    challenges: list[Challenge] = []
    responses: list[Response] = []
    rulings: list[Ruling] = []
    retrieved_ids_by_run: dict[int, list[str]] = {}
    gaps: list[str] = []
    briefing_md: str | None = None

    class Config:
        use_enum_values = True
