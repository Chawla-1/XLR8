"""
Header and paragraph parser shared across TXT, PDF, and DOCX formats.

Every document in the corpus has the same structure:
    KEY: VALUE
    KEY: VALUE
    ---
    Title
    
    [P1] First paragraph...
    [P2] Second paragraph...

This module extracts both the metadata header and the tagged paragraphs.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date


def parse_header(raw_text: str) -> tuple[dict[str, str], str]:
    """
    Split raw document text into header metadata and body.
    
    Returns:
        (header_dict, body_text)
        header_dict keys are normalised to lowercase: doc_id, event_id, title, etc.
    """
    # Split on the --- separator
    parts = re.split(r'\n---\s*\n', raw_text, maxsplit=1)
    
    if len(parts) < 2:
        # No header separator found — treat entire text as body
        return {}, raw_text.strip()
    
    header_section = parts[0]
    body = parts[1].strip()
    
    header: dict[str, str] = {}
    for line in header_section.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^([A-Z_]+)\s*:\s*(.+)$', line)
        if match:
            key = match.group(1).lower()  # DOC_ID -> doc_id
            value = match.group(2).strip()
            header[key] = value
    
    return header, body


def parse_paragraphs(body: str) -> dict[str, str]:
    """
    Extract tagged paragraphs from the document body.
    
    Paragraphs are tagged as [P1], [P2], etc.
    Returns dict like {"P1": "First paragraph text...", "P2": "..."}
    """
    paragraphs: dict[str, str] = {}
    
    # Find all [Pn] tagged paragraphs
    # Pattern: [P<number>] followed by text until the next [P<number>] or end
    pattern = r'\[P(\d+)\]\s*(.*?)(?=\[P\d+\]|\Z)'
    matches = re.findall(pattern, body, re.DOTALL)
    
    for num, text in matches:
        key = f"P{num}"
        paragraphs[key] = text.strip()
    
    return paragraphs


def compute_sha256(content: str | bytes) -> str:
    """Compute SHA256 hash of content for dedup detection."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def safe_parse_date(date_str: str) -> date | None:
    """Parse a date string in YYYY-MM-DD format, return None on failure."""
    try:
        return date.fromisoformat(date_str.strip())
    except (ValueError, AttributeError):
        return None


def safe_parse_int(val: str, default: int = 0) -> int:
    """Parse an integer string, return default on failure."""
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return default
