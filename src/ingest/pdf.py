"""
PDF file parser using pdfplumber.

Extracts all text from the PDF, then passes it to the shared header parser.
pdfplumber is chosen for its accuracy on structured documents with metadata headers.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from src.ingest.header import parse_header, parse_paragraphs, compute_sha256


def parse_pdf(file_path: Path) -> tuple[dict[str, str], dict[str, str], str, str]:
    """
    Parse a PDF document file.
    
    Returns:
        (header_dict, paragraphs_dict, full_body_text, sha256_hash)
    
    Raises:
        ValueError: if file is empty or unreadable
    """
    try:
        text_pages: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_pages.append(page_text)
        
        raw = "\n".join(text_pages)
    except Exception as e:
        raise ValueError(f"Failed to read PDF {file_path.name}: {e}")
    
    if not raw.strip():
        raise ValueError(f"Empty PDF: {file_path.name}")
    
    content_hash = compute_sha256(raw)
    header, body = parse_header(raw)
    paragraphs = parse_paragraphs(body)
    
    return header, paragraphs, body, content_hash
