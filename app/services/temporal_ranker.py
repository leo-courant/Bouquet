"""Temporal ranking service for time-aware retrieval."""

from datetime import datetime
from typing import Optional

from loguru import logger

from app.domain import Chunk, SearchResult


class TemporalRanker:
    """Service for ranking results based on temporal information."""

    def __init__(
        self,
        decay_factor: float = 0.95,
        enable_recency_boost: bool = True,
    ) -> None:
        """Initialize temporal ranker."""
        self.decay_factor = decay_factor
        self.enable_recency_boost = enable_recency_boost
        logger.info(f"Initialized TemporalRanker with decay_factor={decay_factor}")

    def apply_temporal_ranking(
        self,
        results: list[SearchResult],
        query_time: Optional[datetime] = None,
        prefer_recent: bool = True,
    ) -> list[SearchResult]:
        """Apply temporal ranking to search results."""
        if query_time is None:
            query_time = datetime.utcnow()
        
        # Score and re-rank based on temporal information
        for result in results:
            temporal_score = self._compute_temporal_score(
                result,
                query_time,
                prefer_recent,
            )
            
            # Combine with existing score
            original_score = result.score
            result.score = original_score * temporal_score
            
            # Store temporal metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata['temporal_score'] = temporal_score
            result.metadata['original_score'] = original_score
        
        # Re-sort by adjusted scores
        results.sort(key=lambda x: x.score, reverse=True)
        
        logger.debug(f"Applied temporal ranking to {len(results)} results")
        return results

    def _compute_temporal_score(
        self,
        result: SearchResult,
        query_time: datetime,
        prefer_recent: bool,
    ) -> float:
        """Compute temporal relevance score for a result."""
        # Try to extract timestamp from metadata
        chunk_time = self._extract_timestamp(result)
        
        if chunk_time is None:
            return 1.0  # No temporal info, no adjustment
        
        # Compute time difference (in days)
        time_diff = abs((query_time - chunk_time).days)
        
        if prefer_recent:
            # Exponential decay for older content
            # More recent = higher score
            score = self.decay_factor ** (time_diff / 365.0)  # Yearly decay
        else:
            # Inverse: older content may be preferred (historical queries)
            score = 1.0 - (self.decay_factor ** (time_diff / 365.0))
            score = max(0.5, score)  # Don't penalize too much
        
        return max(0.5, min(1.5, score))  # Bounded adjustment

    def _extract_timestamp(self, result: SearchResult) -> Optional[datetime]:
        """Extract timestamp from result metadata."""
        if result.metadata:
            # Check various possible timestamp fields
            for field in ['timestamp', 'created_at', 'updated_at', 'date', 'temporal_start']:
                if field in result.metadata:
                    value = result.metadata[field]
                    if isinstance(value, datetime):
                        return value
                    elif isinstance(value, str):
                        try:
                            return datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            continue
        
        return None

    def filter_by_temporal_range(
        self,
        results: list[SearchResult],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[SearchResult]:
        """Filter results by temporal range."""
        if start_time is None and end_time is None:
            return results
        
        filtered = []
        for result in results:
            chunk_time = self._extract_timestamp(result)
            
            if chunk_time is None:
                # Keep results without timestamp
                filtered.append(result)
                continue
            
            # Check if in range
            if start_time and chunk_time < start_time:
                continue
            if end_time and chunk_time > end_time:
                continue
            
            filtered.append(result)
        
        logger.info(f"Filtered to {len(filtered)}/{len(results)} results by temporal range")
        return filtered

    def detect_temporal_query(self, query: str) -> dict:
        """Detect temporal intent in query."""
        query_lower = query.lower()
        
        temporal_indicators = {
            'recent': ['recent', 'latest', 'current', 'now', 'today', 'this year'],
            'historical': ['history', 'past', 'originally', 'first', 'early', 'initially'],
            'before': ['before', 'prior to', 'earlier than', 'preceding'],
            'after': ['after', 'since', 'following', 'later than'],
            'between': ['between', 'during', 'from', 'to'],
            'when': ['when', 'what year', 'what date', 'what time'],
        }
        
        detected = {
            'is_temporal': False,
            'temporal_type': None,
            'prefer_recent': False,
            'keywords': [],
        }
        
        for temporal_type, keywords in temporal_indicators.items():
            found = [kw for kw in keywords if kw in query_lower]
            if found:
                detected['is_temporal'] = True
                detected['temporal_type'] = temporal_type
                detected['keywords'].extend(found)
                
                if temporal_type in ['recent', 'after']:
                    detected['prefer_recent'] = True
                elif temporal_type in ['historical', 'before']:
                    detected['prefer_recent'] = False
        
        if detected['is_temporal']:
            logger.info(f"Detected temporal query: {detected['temporal_type']}")
        
        return detected
