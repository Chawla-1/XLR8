"""
BM25 search index with metadata filters.

Provides hybrid search: BM25 text relevance + hard metadata filters 
(event_id, country, sector, tier, clock).

The clock filter is applied IN CODE, not by asking the LLM — 
this makes clock violations impossible.
"""

from __future__ import annotations

import re
from datetime import date

from rank_bm25 import BM25Okapi

from src.core.schemas import Document, DocStatus


class SearchIndex:
    """
    BM25-based search index over parsed documents.
    Supports metadata filtering on event_id, country, sector, tier, and date.
    """
    
    def __init__(self, documents: list[Document]):
        """
        Build the index from a list of Documents.
        Only indexes documents with status OK.
        """
        self.all_docs = documents
        self.active_docs = [d for d in documents if d.status == DocStatus.OK]
        
        # Tokenize for BM25
        self._corpus = [
            self._tokenize(f"{d.title} {d.text}")
            for d in self.active_docs
        ]
        
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None
        
        # Build lookup indexes
        self._by_id: dict[str, Document] = {d.doc_id: d for d in documents}
    
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + lowercase tokenizer."""
        return re.findall(r'\w+', text.lower())
    
    def get_doc(self, doc_id: str) -> Document | None:
        """Retrieve a single document by ID."""
        return self._by_id.get(doc_id)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        *,
        event_id: str | None = None,
        country: str | None = None,
        sector: str | None = None,
        max_tier: int | None = None,
        as_of: date | None = None,
        exclude_ids: set[str] | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Search for documents matching the query with optional filters.
        
        Args:
            query: search text
            top_k: max results to return
            event_id: filter by event (e.g., "E5")
            country: filter by country (e.g., "Midgard")
            sector: filter by sector (e.g., "Wheat")
            max_tier: only include docs with reliability <= this value
            as_of: exclude docs published after this date (CLOCK FILTER)
            exclude_ids: doc IDs to exclude (for Run 2 dedup)
        
        Returns:
            List of (Document, score) tuples, sorted by relevance
        """
        if not self._bm25 or not self.active_docs:
            return []
        
        # BM25 scoring
        query_tokens = self._tokenize(query)
        scores = self._bm25.get_scores(query_tokens)
        
        # Pair docs with scores and filter
        results: list[tuple[Document, float]] = []
        
        for doc, score in zip(self.active_docs, scores):
            # Hard metadata filters (applied in code, not prompt)
            if event_id is not None and doc.event_id != event_id and doc.event_id != "NONE":
                # Allow NONE event_id docs (atlas/background) through
                if event_id != "NONE":
                    continue
            
            if country is not None and doc.country.lower() != country.lower():
                continue
            
            if sector is not None and doc.sector.lower() != sector.lower() and doc.sector.lower() != "general":
                continue
            
            if max_tier is not None and doc.reliability > max_tier:
                continue
            
            # CLOCK FILTER — this is critical for scoring
            if as_of is not None and doc.pub_date > as_of:
                continue
            
            if exclude_ids and doc.doc_id in exclude_ids:
                continue
            
            results.append((doc, score))
        
        # Sort by BM25 score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def filter_docs(
        self,
        *,
        event_id: str | None = None,
        country: str | None = None,
        sector: str | None = None,
        source_type: str | None = None,
        max_tier: int | None = None,
        as_of: date | None = None,
    ) -> list[Document]:
        """
        Filter documents by metadata without text search.
        Useful for retrieving all trade notes for a route, etc.
        """
        results = []
        for doc in self.active_docs:
            if event_id is not None and doc.event_id != event_id and doc.event_id != "NONE":
                continue
            if country is not None and doc.country.lower() != country.lower():
                continue
            if sector is not None and doc.sector.lower() != sector.lower() and doc.sector.lower() != "general":
                continue
            if source_type is not None and doc.source_type.lower() != source_type.lower():
                continue
            if max_tier is not None and doc.reliability > max_tier:
                continue
            if as_of is not None and doc.pub_date > as_of:
                continue
            results.append(doc)
        return results
    
    @property
    def doc_count(self) -> int:
        return len(self.active_docs)
    
    @property
    def total_count(self) -> int:
        return len(self.all_docs)
