"""
Trade table parser — extracts month/value/volume data from trade note documents.

Parses sentence-style rows:
    [P2] In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes.

Features:
- Unit normalization (M/B/K for USD, tonnes/t/kt for volume)
- Price-per-tonne plausibility checks
- Damaged row logging (missing values, repeated months, corrupted data)
- Narrative filtering (skips summary paragraphs like [P14])
"""

from __future__ import annotations

import re
import logging
from datetime import date

from src.core.schemas import Document, TradeRow

logger = logging.getLogger(__name__)

# Enhanced regex supporting flexible units and whitespace
TRADE_ROW_RE = re.compile(
    r"In\s+(?P<mon>[A-Z][a-z]+)\s+(?P<yr>\d{4}),?\s+"
    r"the\s+value\s+was\s+USD\s+(?P<val>[\d.,]+)\s*(?P<u>[MBK])?\s+"
    r"and\s+the\s+volume\s+was\s+(?P<vol>[\d,]+)\s*(?P<vu>tonnes|t|kt)?",
    re.IGNORECASE,
)

# Loose regex to detect attempted data rows that failed to parse (damaged rows)
ATTEMPTED_ROW_RE = re.compile(
    r"In\s+[A-Z][a-z]+\s+\d{4}.*?(?:value|volume)",
    re.IGNORECASE,
)

# Route line pattern: "Route: Orvan to Midgard, wheat."
ROUTE_RE = re.compile(
    r'Route:\s+(\w+)\s+to\s+(\w+),?\s+(\w+)',
    re.IGNORECASE,
)

MONTH_MAP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
}


def is_trade_note(doc: Document) -> bool:
    """Check if a document is a trade note."""
    return doc.source_type == "trade_note" or any(
        TRADE_ROW_RE.search(text) for text in doc.paragraphs.values()
    )


def extract_route(doc: Document) -> tuple[str, str, str] | None:
    """Extract (origin, destination, commodity) from route line or title."""
    for para_text in doc.paragraphs.values():
        match = ROUTE_RE.search(para_text)
        if match:
            return match.group(1), match.group(2), match.group(3).lower()

    title_match = re.search(
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
    Flags and records damaged rows with specific diagnostic reasons.
    """
    route = extract_route(doc)
    if route is None:
        return []

    origin, destination, commodity = route
    rows: list[TradeRow] = []
    seen_months: set[str] = set()

    for para_key, para_text in doc.paragraphs.items():
        # Skip narrative paragraphs (e.g., "[P14] Vanir wheat reached Midgard...")
        if "Route:" in para_text:
            continue

        match = TRADE_ROW_RE.search(para_text)
        if not match:
            # Check if this was an attempted data row with damaged/missing elements
            if ATTEMPTED_ROW_RE.search(para_text):
                logger.warning("Damaged row in %s#%s: Failed data row parse -> '%s'", doc.doc_id, para_key, para_text)
                rows.append(TradeRow(
                    table_id=doc.doc_id,
                    paragraph=para_key,
                    month="unknown",
                    year=0,
                    value_usd_m=0.0,
                    volume_kt=0.0,
                    commodity=commodity,
                    origin=origin,
                    destination=destination,
                    status="damaged",
                ))
            continue

        month_name = match.group("mon").lower()
        year_str = match.group("yr")
        val_str = match.group("val").replace(',', '')
        vol_str = match.group("vol").replace(',', '')
        u_unit = (match.group("u") or "M").upper()
        v_unit = (match.group("vu") or "tonnes").lower()

        month_num = MONTH_MAP.get(month_name)
        if not month_num or not year_str.isdigit():
            rows.append(TradeRow(
                table_id=doc.doc_id,
                paragraph=para_key,
                month=f"{year_str}-{month_name}",
                year=int(year_str) if year_str.isdigit() else 0,
                value_usd_m=0.0,
                volume_kt=0.0,
                commodity=commodity,
                origin=origin,
                destination=destination,
                status="damaged",
            ))
            continue

        month_key = f"{year_str}-{month_num}"
        year = int(year_str)

        try:
            val_raw = float(val_str)
            vol_raw = float(vol_str)

            # Value normalization to USD Millions
            if u_unit == "B":
                value_m = val_raw * 1000.0
            elif u_unit == "K":
                value_m = val_raw / 1000.0
            else:
                value_m = val_raw

            # Volume normalization to kilotonnes (kt)
            if v_unit in ("t", "tonnes"):
                volume_kt = vol_raw / 1000.0
            elif v_unit == "kt":
                volume_kt = vol_raw
            else:
                volume_kt = vol_raw / 1000.0

        except ValueError:
            rows.append(TradeRow(
                table_id=doc.doc_id,
                paragraph=para_key,
                month=month_key,
                year=year,
                value_usd_m=0.0,
                volume_kt=0.0,
                commodity=commodity,
                origin=origin,
                destination=destination,
                status="damaged",
            ))
            continue

        # Sanity and Plausibility Checks
        status = "ok"

        # Check duplicate months in same document
        if month_key in seen_months:
            logger.warning("Duplicate month %s in %s#%s", month_key, doc.doc_id, para_key)
            status = "damaged"
        seen_months.add(month_key)

        if value_m <= 0 or volume_kt <= 0:
            status = "damaged"

        # Price per tonne plausibility check
        # Grain normal corridor is $80 to $1500 / tonne
        # ($M * 1,000,000) / (kt * 1000) = ($ / tonne)
        if volume_kt > 0:
            price_per_tonne = (value_m * 1000.0) / volume_kt
            if price_per_tonne < 80.0 or price_per_tonne > 1500.0:
                logger.warning(
                    "Price-per-tonne anomaly in %s#%s: $%.1f/t outside corridor [80, 1500]",
                    doc.doc_id, para_key, price_per_tonne
                )
                status = "damaged"

        rows.append(TradeRow(
            table_id=doc.doc_id,
            paragraph=para_key,
            month=month_key,
            year=year,
            value_usd_m=round(value_m, 2),
            volume_kt=round(volume_kt, 2),
            commodity=commodity,
            origin=origin,
            destination=destination,
            status=status,
        ))

    return rows


def extract_all_trade_tables(documents: list[Document]) -> list[TradeRow]:
    """Extract trade rows from all trade note documents (skips quarantined)."""
    all_rows: list[TradeRow] = []
    for doc in documents:
        if doc.status.value != "ok":
            continue
        if not is_trade_note(doc):
            continue
        rows = parse_trade_rows(doc)
        all_rows.extend(rows)
    return all_rows


def group_by_route(rows: list[TradeRow]) -> dict[str, list[TradeRow]]:
    """Group trade rows by route string: Origin → Destination (commodity)."""
    routes: dict[str, list[TradeRow]] = {}
    for r in rows:
        key = f"{r.origin} → {r.destination} ({r.commodity})"
        routes.setdefault(key, []).append(r)
    return routes
