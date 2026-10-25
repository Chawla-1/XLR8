"""
Main ingestion pipeline — orchestrates parsing all documents in a pack folder.

Takes a pack directory (e.g., dev_pack_E5/), reads manifest.json,
parses every file in docs/, quarantines bad ones, and returns a list
of Document objects ready for indexing.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from src.core.schemas import Document, DocStatus
from src.ingest.header import (
    parse_header,
    parse_paragraphs,
    compute_sha256,
    safe_parse_date,
    safe_parse_int,
)
from src.ingest.quarantine import quarantine_documents, get_quarantine_report

logger = logging.getLogger(__name__)


def _parse_file(file_path: Path) -> tuple[dict[str, str], dict[str, str], str, str]:
    """
    Dispatch to the correct parser based on file extension.
    Returns (header, paragraphs, body, sha256).
    """
    ext = file_path.suffix.lower()
    
    if ext == ".txt":
        from src.ingest.txt import parse_txt
        return parse_txt(file_path)
    elif ext == ".pdf":
        from src.ingest.pdf import parse_pdf
        return parse_pdf(file_path)
    elif ext == ".docx":
        from src.ingest.docx_parser import parse_docx
        return parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def _build_document(
    header: dict[str, str],
    paragraphs: dict[str, str],
    body: str,
    sha256: str,
    file_path: Path,
    manifest_entry: dict | None = None,
) -> Document:
    """
    Build a Document from parsed header + manifest metadata.
    Manifest takes priority for structured fields; header is the fallback.
    """
    # Prefer manifest fields (uppercase keys) with header fallback
    def get(key: str, default: str = "") -> str:
        if manifest_entry:
            # manifest has both uppercase and lowercase for ORV docs
            val = manifest_entry.get(key.upper()) or manifest_entry.get(key.lower())
            if val is not None:
                return str(val).strip()
        return header.get(key.lower(), default).strip()
    
    pub_date = safe_parse_date(get("pub_date", "1900-01-01"))
    if pub_date is None:
        pub_date = date(1900, 1, 1)
    
    reliability = safe_parse_int(get("reliability", "0"))
    
    return Document(
        doc_id=get("doc_id", file_path.stem),
        event_id=get("event_id", "NONE"),
        title=get("title", "Untitled"),
        source_name=get("source_name", "Unknown"),
        source_type=get("source_type", "unknown"),
        reliability=reliability,
        pub_date=pub_date,
        pub_time=get("pub_time", "00:00"),
        country=get("country", "Unknown"),
        sector=get("sector", "general"),
        language=get("language", "en"),
        file_path=str(file_path.relative_to(file_path.parent.parent)),
        file_format=file_path.suffix.lstrip(".").upper(),
        text=body,
        paragraphs=paragraphs,
        sha256=sha256,
        status=DocStatus.OK,
    )


def load_manifest(pack_dir: Path) -> dict[str, dict]:
    """Load manifest.json and return a dict keyed by DOC_ID."""
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        logger.warning("No manifest.json found in %s", pack_dir)
        return {}
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    manifest: dict[str, dict] = {}
    for entry in data.get("documents", []):
        doc_id = entry.get("DOC_ID") or entry.get("doc_id", "")
        if doc_id:
            manifest[doc_id] = entry
    
    return manifest


def ingest_pack(
    pack_dir: Path,
    as_of: date | None = None,
) -> tuple[list[Document], dict]:
    """
    Ingest an entire event pack.
    
    Args:
        pack_dir: Path to the pack directory (e.g., dev_pack_E5/)
        as_of: The as-of date for clock filtering (default: from manifest)
    
    Returns:
        (documents, quarantine_report)
        documents: list of all Document objects (including quarantined ones)
        quarantine_report: summary of what was flagged
    """
    docs_dir = pack_dir / "docs"
    if not docs_dir.exists():
        raise FileNotFoundError(f"No docs/ folder in {pack_dir}")
    
    # Load manifest for metadata cross-reference
    manifest = load_manifest(pack_dir)
    
    # Determine as_of date
    if as_of is None:
        manifest_path = pack_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            as_of_str = meta.get("as_of", "2027-01-25")
            as_of = date.fromisoformat(as_of_str)
        else:
            as_of = date(2027, 1, 25)  # default
    
    # Parse all files
    documents: list[Document] = []
    parse_errors: list[dict] = []
    
    all_files = sorted(docs_dir.iterdir())
    logger.info("Found %d files in %s", len(all_files), docs_dir)
    
    for file_path in all_files:
        if file_path.is_dir() or file_path.suffix.lower() not in ('.txt', '.pdf', '.docx'):
            continue
        
        doc_id = file_path.stem  # e.g., "ORV-0009"
        manifest_entry = manifest.get(doc_id)
        
        try:
            header, paragraphs, body, sha256 = _parse_file(file_path)
            doc = _build_document(header, paragraphs, body, sha256, file_path, manifest_entry)
            documents.append(doc)
            logger.debug("Parsed %s (%s) — %d paragraphs", doc.doc_id, doc.file_format, len(paragraphs))
            
        except ValueError as e:
            # File is empty or unparseable — create a damaged document
            logger.warning("Parse error for %s: %s", file_path.name, e)
            damaged_doc = Document(
                doc_id=doc_id,
                event_id=manifest_entry.get("EVENT_ID", "NONE") if manifest_entry else "NONE",
                title=manifest_entry.get("TITLE", "Unknown") if manifest_entry else "Unknown",
                source_name="Unknown",
                source_type="unknown",
                reliability=0,
                pub_date=date(1900, 1, 1),
                pub_time="00:00",
                country="Unknown",
                sector="general",
                file_path=str(file_path.name),
                file_format=file_path.suffix.lstrip(".").upper(),
                text="",
                paragraphs={},
                sha256="",
                status=DocStatus.DAMAGED,
                quarantine_reason=str(e),
            )
            documents.append(damaged_doc)
            parse_errors.append({"file": file_path.name, "error": str(e)})
        
        except Exception as e:
            logger.error("Unexpected error parsing %s: %s", file_path.name, e)
            parse_errors.append({"file": file_path.name, "error": str(e)})
    
    # Validate against manifest — check for docs in manifest but not on disk
    parsed_ids = {d.doc_id for d in documents}
    for manifest_id in manifest:
        if manifest_id not in parsed_ids:
            logger.warning("Manifest lists %s but no file was found/parsed", manifest_id)
    
    # Run quarantine checks
    quarantine_documents(documents, as_of)
    report = get_quarantine_report(documents)
    report["parse_errors"] = parse_errors
    
    logger.info(
        "Ingestion complete: %d total, %d ok, %d quarantined, %d parse errors",
        report["total"], report["ok"], len(report["quarantined"]), len(parse_errors),
    )
    
    return documents, report
