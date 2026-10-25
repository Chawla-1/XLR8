"""
Trade table parser — extracts month/value/volume data from trade note documents.

Trade notes have a specific pattern in their paragraphs:
    [P1] Route: Orvan to Midgard, wheat.
    [P2] In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes.
    [P3] In August 2026, the value was USD 96.1M and the volume was 267,000 tonnes.

This parser extracts structured TradeRow objects from these paragraphs.
"""

from __future__ import annotations

import re
from datetime import date

from src.core.schemas import Document, TradeRow

# Pattern to match trade data paragraphs
# "In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes."
TRADE_ROW_RE = re.compile(
    r'In\s+(\w+)\s+(\d{4}),?\s+'
    r'the\s+value\s+was\s+USD\s+([\d,.]+)M\s+'
    r'and\s+the\s+volume\s+was\s+([\d,.]+)\s+tonnes',
    re.IGNORECASE,
)

# Pattern to extract route info
# "Route: Orvan to Midgard, wheat."
ROUTE_RE = re.compile(
    r'Route:\s+(\w+)\s+to\s+(\w+),?\s+(\w+)',
    re.IGNORECASE,
)

# Month name to number mapping
MONTH_MAP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
}


def is_trade_note(doc: Document) -> bool:
    """Check if a document is a trade note (contains tabular trade data)."""
    return doc.source_type == "trade_note" or any(
        TRADE_ROW_RE.search(text) for text in doc.paragraphs.values()
    )


def extract_route(doc: Document) -> tuple[str, str, str] | None:
    """
    Extract (origin, destination, commodity) from a trade note's route line.
    Falls back to title parsing if no explicit route paragraph.
    """
    # Try P1 first (usually the route line)
    for para_text in doc.paragraphs.values():
        match = ROUTE_RE.search(para_text)
        if match:
            return match.group(1), match.group(2), match.group(3).lower()
    
    # Fall back to title: "Trade note: Orvan to Midgard, wheat, July to December 2026"
    title_match = re.match(
        r'Trade\s+note:\s+(\w+)\s+to\s+(\w+),?\s+(\w+)',
        doc.title,
        re.IGNORECASE,
    )
    if title_match:
        return title_match.group(1), title_match.group(2), title_match.group(3).lower()
    
    return None


def parse_trade_rows(doc: Document) -> list[TradeRow]:
    """
    Extract all trade data rows from a trade note document.
    
    Returns list of TradeRow objects, one per month found.
    Flags damaged rows (missing values, impossible numbers).
    """
    route = extract_route(doc)
    if route is None:
        return []
    
    origin, destination, commodity = route
    rows: list[TradeRow] = []
    
    for para_key, para_text in doc.paragraphs.items():
        match = TRADE_ROW_RE.search(para_text)
        if not match:
            continue
        
        month_name = match.group(1).lower()
        year_str = match.group(2)
        value_str = match.group(3).replace(',', '')
        volume_str = match.group(4).replace(',', '')
        
        # Validate month
        month_num = MONTH_MAP.get(month_name)
        if month_num is None:
            continue
        
        # Parse numbers
        try:
            value = float(value_str)
            volume = float(volume_str) / 1000.0  # convert tonnes to kt
            year = int(year_str)
        except ValueError:
            # Damaged row
            rows.append(TradeRow(
                table_id=doc.doc_id,
                paragraph=para_key,
                month=f"{year_str}-{month_num}",
                year=int(year_str) if year_str.isdigit() else 0,
                value_usd_m=0.0,
                volume_kt=0.0,
                commodity=commodity,
                origin=origin,
                destination=destination,
                status="damaged",
            ))
            continue
        
        # Sanity checks
        status = "ok"
        if value <= 0 or volume <= 0:
            status = "damaged"
        if value > 10000:  # > $10 billion seems wrong
            status = "damaged"
        
        rows.append(TradeRow(
            table_id=doc.doc_id,
            paragraph=para_key,
            month=f"{year_str}-{month_num}",
            year=year,
            value_usd_m=value,
            volume_kt=volume,
            commodity=commodity,
            origin=origin,
            destination=destination,
            status=status,
        ))
    
    return rows


def extract_all_trade_tables(documents: list[Document]) -> list[TradeRow]:
    """
    Extract trade rows from all trade note documents.
    Skips quarantined documents.
    """
    all_rows: list[TradeRow] = []
    
    for doc in documents:
        if doc.status.value != "ok":
            continue
        if not is_trade_note(doc):
            continue
        
        rows = parse_trade_rows(doc)
        all_rows.extend(rows)
    
    return all_rows
