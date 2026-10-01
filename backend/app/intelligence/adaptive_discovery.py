from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models import ScrapeJobExecutionLog

logger = logging.getLogger(__name__)


class AdaptiveDiscoveryEngine:
    @staticmethod
    def get_source_score(db: Session, source_name: str) -> float:
        """Calculate historical success score for a source based on execution logs."""
        try:
            logs = db.scalars(
                select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.source == source_name)
            ).all()
        except Exception:
            return 1.0
        
        if not logs or not isinstance(logs, list):
            return 1.0
            
        total_received = 0
        total_new = 0
        total_failed = 0
        for log in logs:
            total_received += getattr(log, "records_received", 0) or 0
            total_new += getattr(log, "new_count", 0) or 0
            total_failed += getattr(log, "failed_count", 0) or 0
            
        n = len(logs)
        if n == 0:
            return 1.0
        avg_received = total_received / n
        avg_new = total_new / n
        avg_failed = total_failed / n
        
        score = (avg_received + avg_new * 2.0) / (1.0 + avg_failed)
        return float(score)

    @staticmethod
    def get_query_score(db: Session, query_term: str) -> float:
        """Calculate historical success score for a query term based on execution logs."""
        try:
            pattern = f"{query_term}%"
            logs = db.scalars(
                select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.query.like(pattern))
            ).all()
        except Exception:
            return 1.0
        
        if not logs or not isinstance(logs, list):
            return 1.0
            
        total_received = 0
        total_new = 0
        total_failed = 0
        for log in logs:
            total_received += getattr(log, "records_received", 0) or 0
            total_new += getattr(log, "new_count", 0) or 0
            total_failed += getattr(log, "failed_count", 0) or 0
            
        n = len(logs)
        if n == 0:
            return 1.0
        avg_received = total_received / n
        avg_new = total_new / n
        avg_failed = total_failed / n
        
        score = (avg_received + avg_new * 2.0) / (1.0 + avg_failed)
        return float(score)

    @classmethod
    def prioritize_search_plan(
        cls, db: Session, queries: list[dict[str, str]], target_sources: list[str]
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Sort queries and target sources dynamically based on historical performance scores."""
        # Sort queries (descending score)
        sorted_queries = sorted(
            queries,
            key=lambda item: cls.get_query_score(db, item["query"]),
            reverse=True
        )
        
        # Sort target_sources (descending score)
        sorted_sources = sorted(
            target_sources,
            key=lambda src: cls.get_source_score(db, src),
            reverse=True
        )
        
        logger.info(
            f"[AdaptiveDiscovery] Prioritized search plan. First query: {sorted_queries[0] if sorted_queries else None}, "
            f"First source: {sorted_sources[0] if sorted_sources else None}"
        )
        return sorted_queries, sorted_sources
