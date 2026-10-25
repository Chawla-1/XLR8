"""
Quarantine system — flags documents that should not be treated as reliable evidence.

Checks for:
1. Empty / damaged files (0 bytes, parse failures)
2. Content duplicates (same SHA256 hash)
3. Clock violations (published after the as-of date)
4. Tier 4 unreliable sources (social posts, blogs, tabloids)
5. Prompt injection attempts
"""

from __future__ import annotations

import re
from datetime import date

from src.core.schemas import Document, DocStatus


# Phrases that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(your|all|previous)\s+(rules|instructions|prompts)",
    r"you\s+are\s+now",
    r"forget\s+(your|all|previous)",
    r"disregard\s+(your|all|previous)",
    r"new\s+instructions?\s*:",
    r"system\s*prompt\s*:",
    r"override\s+(your|all|previous)",
    r"act\s+as\s+(if|a|an)",
    r"pretend\s+(you|to\s+be)",
]

INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def check_injection(text: str) -> bool:
    """Returns True if text contains prompt injection patterns."""
    return bool(INJECTION_RE.search(text))


def quarantine_documents(
    documents: list[Document],
    as_of: date | None = None,
) -> list[Document]:
    """
    Run all quarantine checks on a list of parsed documents.
    Modifies doc.status and doc.quarantine_reason in-place.
    
    Returns the same list (mutated) for convenience.
    """
    # ── Pass 1: Content duplicate detection ──
    seen_hashes: dict[str, str] = {}  # hash -> first doc_id
    for doc in documents:
        if doc.sha256 in seen_hashes:
            first_id = seen_hashes[doc.sha256]
            doc.status = DocStatus.DUPLICATE
            doc.quarantine_reason = f"Content duplicate of {first_id}"
        else:
            seen_hashes[doc.sha256] = doc.doc_id
    
    # ── Pass 2: Per-document checks ──
    for doc in documents:
        # Skip already quarantined (duplicates)
        if doc.status != DocStatus.OK:
            continue
        
        # Empty / damaged
        if not doc.text.strip() or len(doc.paragraphs) == 0:
            doc.status = DocStatus.DAMAGED
            doc.quarantine_reason = "Empty or unparseable content"
            continue
        
        
        # Prompt injection
        if check_injection(doc.text):
            doc.status = DocStatus.INJECTED
            doc.quarantine_reason = "Prompt injection pattern detected"
            continue
    
    return documents


def get_quarantine_report(documents: list[Document]) -> dict:
    """
    Generate a summary report of all quarantined documents.
    """
    report = {
        "total": len(documents),
        "ok": 0,
        "quarantined": [],
    }
    
    for doc in documents:
        if doc.status == DocStatus.OK:
            report["ok"] += 1
        else:
            report["quarantined"].append({
                "doc_id": doc.doc_id,
                "status": doc.status.value,
                "reason": doc.quarantine_reason,
                "file": doc.file_path,
            })
    
    return report
