"""
DOCX file parser using python-docx.

Extracts all paragraph text from the DOCX, then passes it to the shared header parser.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument

from src.ingest.header import parse_header, parse_paragraphs, compute_sha256


def parse_docx(file_path: Path) -> tuple[dict[str, str], dict[str, str], str, str]:
    """
    Parse a DOCX document file.
    
    Returns:
        (header_dict, paragraphs_dict, full_body_text, sha256_hash)
    
    Raises:
        ValueError: if file is empty or unreadable
    """
    try:
        doc = DocxDocument(str(file_path))
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        raw = "\n".join(lines)
    except Exception as e:
        raise ValueError(f"Failed to read DOCX {file_path.name}: {e}")
    
    if not raw.strip():
        raise ValueError(f"Empty DOCX: {file_path.name}")
    
    content_hash = compute_sha256(raw)
    header, body = parse_header(raw)
    paragraphs = parse_paragraphs(body)
    
    return header, paragraphs, body, content_hash
