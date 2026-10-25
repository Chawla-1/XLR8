"""
TXT file parser.
TXT files are the simplest — just read and pass to the shared header parser.
"""

from __future__ import annotations

from pathlib import Path

from src.ingest.header import parse_header, parse_paragraphs, compute_sha256


def parse_txt(file_path: Path) -> tuple[dict[str, str], dict[str, str], str, str]:
    """
    Parse a TXT document file.
    
    Returns:
        (header_dict, paragraphs_dict, full_body_text, sha256_hash)
    
    Raises:
        ValueError: if file is empty or unreadable
    """
    raw = file_path.read_text(encoding='utf-8', errors='replace')
    
    if not raw.strip():
        raise ValueError(f"Empty file: {file_path.name}")
    
    content_hash = compute_sha256(raw)
    header, body = parse_header(raw)
    paragraphs = parse_paragraphs(body)
    
    return header, paragraphs, body, content_hash
