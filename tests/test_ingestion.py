"""
Test script for the data ingestion layer.
Run from the project root: python -m tests.test_ingestion
"""

import sys
import os
import json
from pathlib import Path
from datetime import date

# Force UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingest.pipeline import ingest_pack, load_manifest
from src.index.bm25 import SearchIndex
from src.calc.tables import extract_all_trade_tables, is_trade_note


def main():
    pack_dir = Path("03_Ragnarok Trial of the Nine Realms/dev_pack_E5")
    as_of = date(2027, 1, 25)
    
    print("=" * 70)
    print("INGESTION PIPELINE TEST")
    print("=" * 70)
    
    # ── Step 1: Ingest all documents ──
    print("\n[1] Ingesting documents...")
    documents, report = ingest_pack(pack_dir, as_of)
    
    print(f"    Total files parsed: {report['total']}")
    print(f"    OK documents:       {report['ok']}")
    print(f"    Quarantined:        {len(report['quarantined'])}")
    print(f"    Parse errors:       {len(report.get('parse_errors', []))}")
    
    # ── Step 2: Quarantine report ──
    print("\n[2] Quarantine Report:")
    for item in report["quarantined"]:
        print(f"    ❌ {item['doc_id']:12s}  status={item['status']:20s}  reason={item['reason']}")
    
    if report.get("parse_errors"):
        print("\n    Parse Errors:")
        for err in report["parse_errors"]:
            print(f"    ⚠️  {err['file']}: {err['error']}")
    
    # ── Step 3: Check specific documents we know about ──
    print("\n[3] Spot Checks:")
    docs_by_id = {d.doc_id: d for d in documents}
    
    # ORV-0023 should be damaged (empty)
    if "ORV-0023" in docs_by_id:
        d = docs_by_id["ORV-0023"]
        status = "✅ PASS" if d.status.value in ("damaged", "quarantined") else "❌ FAIL"
        print(f"    {status} ORV-0023 (empty file):      status={d.status.value}")
    
    # ORV-0040 should be duplicate of ORV-0006
    if "ORV-0040" in docs_by_id:
        d = docs_by_id["ORV-0040"]
        status = "✅ PASS" if d.status.value == "duplicate" else "❌ FAIL"
        print(f"    {status} ORV-0040 (dup of ORV-0006): status={d.status.value}, reason={d.quarantine_reason}")
    
    # ORV-0014 should be clock violation (pub 2027-02-11)
    if "ORV-0014" in docs_by_id:
        d = docs_by_id["ORV-0014"]
        status = "✅ PASS" if d.status.value == "clock_violation" else "❌ FAIL"
        print(f"    {status} ORV-0014 (clock violation):  status={d.status.value}, pub_date={d.pub_date}")
    
    # ORV-0036 should be clock violation (pub 2027-02-22)
    if "ORV-0036" in docs_by_id:
        d = docs_by_id["ORV-0036"]
        status = "✅ PASS" if d.status.value == "clock_violation" else "❌ FAIL"
        print(f"    {status} ORV-0036 (clock violation):  status={d.status.value}, pub_date={d.pub_date}")
    
    # ORV-0041 should be clock violation (pub 2027-04-09)
    if "ORV-0041" in docs_by_id:
        d = docs_by_id["ORV-0041"]
        status = "✅ PASS" if d.status.value == "clock_violation" else "❌ FAIL"
        print(f"    {status} ORV-0041 (clock violation):  status={d.status.value}, pub_date={d.pub_date}")
    
    # ORV-0009 should be OK (Tier 1 trade note)
    if "ORV-0009" in docs_by_id:
        d = docs_by_id["ORV-0009"]
        status = "✅ PASS" if d.status.value == "ok" else "❌ FAIL"
        print(f"    {status} ORV-0009 (good trade note):  status={d.status.value}, paras={len(d.paragraphs)}")
    
    # ── Step 4: Build search index ──
    print("\n[4] Building search index...")
    index = SearchIndex(documents)
    print(f"    Active docs indexed: {index.doc_count}")
    print(f"    Total docs (incl quarantined): {index.total_count}")
    
    # ── Step 5: Test searches ──
    print("\n[5] Search Tests:")
    
    # Search for wheat trade with Midgard
    results = index.search("wheat trade Midgard", top_k=5, event_id="E5", as_of=as_of)
    print(f"\n    Query: 'wheat trade Midgard' (event=E5)")
    for doc, score in results:
        print(f"      {doc.doc_id:12s}  T{doc.reliability}  {doc.title[:50]:50s}  score={score:.2f}")
    
    # Search for corridor agreement
    results = index.search("corridor agreement expired", top_k=5, as_of=as_of)
    print(f"\n    Query: 'corridor agreement expired'")
    for doc, score in results:
        print(f"      {doc.doc_id:12s}  T{doc.reliability}  {doc.title[:50]:50s}  score={score:.2f}")
    
    # Filter: only trade notes for Midgard
    trade_notes = index.filter_docs(source_type="trade_note", country="Midgard", as_of=as_of)
    print(f"\n    Filter: trade_notes for Midgard = {len(trade_notes)} docs")
    for doc in trade_notes:
        print(f"      {doc.doc_id:12s}  {doc.title[:60]}")
    
    # Filter: Tier 4 only (should be flagged as unreliable)
    tier4 = index.filter_docs(event_id="E5", as_of=as_of)
    tier4 = [d for d in tier4 if d.reliability == 4]
    print(f"\n    Tier 4 docs (unreliable): {len(tier4)}")
    for doc in tier4:
        print(f"      {doc.doc_id:12s}  {doc.source_name:20s}  {doc.title[:45]}")
    
    # ── Step 6: Trade table extraction ──
    print("\n[6] Trade Table Extraction:")
    
    trade_rows = extract_all_trade_tables(documents)
    print(f"    Total trade rows extracted: {len(trade_rows)}")
    
    # Group by route
    routes: dict[str, list] = {}
    for row in trade_rows:
        key = f"{row.origin} → {row.destination} ({row.commodity})"
        routes.setdefault(key, []).append(row)
    
    print(f"    Unique trade routes found: {len(routes)}")
    for route_name, rows in sorted(routes.items()):
        ok_rows = [r for r in rows if r.status == "ok"]
        print(f"\n    📊 {route_name} — {len(ok_rows)} data points from {rows[0].table_id}")
        for row in sorted(ok_rows, key=lambda r: r.month):
            print(f"       {row.month}  Value: ${row.value_usd_m:6.1f}M  Volume: {row.volume_kt:.0f}kt  [{row.table_id}#{row.paragraph}]")
    
    # ── Step 7: Quick exposure check on Midgard wheat ──
    print("\n[7] Quick Exposure Check (Midgard Wheat from ORV-0009):")
    midgard_wheat = [r for r in trade_rows if r.destination == "Midgard" and r.commodity == "wheat" and r.table_id == "ORV-0009"]
    
    if midgard_wheat:
        pre = [r for r in midgard_wheat if r.month < "2026-09" and r.year == 2026]
        post = [r for r in midgard_wheat if r.month >= "2026-09" and r.year == 2026]
        
        if pre and post:
            avg_pre_val = sum(r.value_usd_m for r in pre) / len(pre)
            avg_post_val = sum(r.value_usd_m for r in post) / len(post)
            pct_change = ((avg_post_val - avg_pre_val) / avg_pre_val) * 100
            
            print(f"    Baseline (Jul-Aug 2026 avg):  ${avg_pre_val:.1f}M")
            print(f"    Post-event (Sep-Dec 2026 avg): ${avg_post_val:.1f}M")
            print(f"    Value change: {pct_change:+.1f}%")
            
            if abs(pct_change + 62) < 5:  # should be around -62%
                print(f"    ✅ PASS — matches expected ~-62% drop")
            else:
                print(f"    ⚠️  WARNING — expected ~-62%, got {pct_change:.1f}%")
    
    print("\n" + "=" * 70)
    print("INGESTION PIPELINE TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
