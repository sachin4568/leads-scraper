from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models import ScrapeJobExecutionLog

logger = logging.getLogger(__name__)


class AdaptiveDiscoveryEngine:
    @staticmethod
    def get_source_score(db: Session, source_name: str) -> float:
        """Calculate historical success score for a source based on execution logs.
        
        Score is: (average records_received + average new_count * 2) / (1 + average failed_count)
        """
        logs = db.scalars(
            select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.source == source_name)
        ).all()
        
        if not logs:
            return 1.0  # Default score for new/untested sources
            
        total_received = 0
        total_new = 0
        total_failed = 0
        for log in logs:
            total_received += log.records_received or 0
            total_new += log.new_count or 0
            total_failed += log.failed_count or 0
            
        n = len(logs)
        avg_received = total_received / n
        avg_new = total_new / n
        avg_failed = total_failed / n
        
        score = (avg_received + avg_new * 2.0) / (1.0 + avg_failed)
        logger.info(f"[AdaptiveDiscovery] Source {source_name} score: {score:.2f} (based on {n} runs)")
        return score

    @staticmethod
    def get_query_score(db: Session, query_term: str) -> float:
        """Calculate historical success score for a query term based on execution logs."""
        # Query logs where the logged query starts with our query_term
        pattern = f"{query_term}%"
        logs = db.scalars(
            select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.query.like(pattern))
        ).all()
        
        if not logs:
            return 1.0
            
        total_received = 0
        total_new = 0
        total_failed = 0
        for log in logs:
            total_received += log.records_received or 0
            total_new += log.new_count or 0
            total_failed += log.failed_count or 0
            
        n = len(logs)
        avg_received = total_received / n
        avg_new = total_new / n
        avg_failed = total_failed / n
        
        score = (avg_received + avg_new * 2.0) / (1.0 + avg_failed)
        logger.info(f"[AdaptiveDiscovery] Query '{query_term}' score: {score:.2f} (based on {n} runs)")
        return score

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
