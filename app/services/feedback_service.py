"""Relevance feedback and learning service."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from loguru import logger


class FeedbackService:
    """Service for collecting and using relevance feedback."""

    def __init__(
        self,
        feedback_file: str = "data/feedback.json",
        learning_rate: float = 0.1,
    ) -> None:
        """Initialize feedback service."""
        self.feedback_file = Path(feedback_file)
        self.learning_rate = learning_rate
        
        # In-memory storage
        self.feedback_data: dict[str, list[dict]] = defaultdict(list)
        self.chunk_scores: dict[UUID, float] = {}  # Accumulated feedback scores
        
        # Load existing feedback
        self._load_feedback()
        
        logger.info(f"Initialized FeedbackService (learning_rate={learning_rate})")

    def _load_feedback(self) -> None:
        """Load feedback from file."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r') as f:
                    data = json.load(f)
                    self.feedback_data = defaultdict(list, data.get('feedback', {}))
                    
                    # Reconstruct chunk scores
                    scores_data = data.get('chunk_scores', {})
                    self.chunk_scores = {
                        UUID(k): v for k, v in scores_data.items()
                    }
                    
                logger.info(f"Loaded feedback data for {len(self.feedback_data)} queries")
            except Exception as e:
                logger.error(f"Error loading feedback: {e}")

    def _save_feedback(self) -> None:
        """Save feedback to file."""
        try:
            self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'feedback': dict(self.feedback_data),
                'chunk_scores': {
                    str(k): v for k, v in self.chunk_scores.items()
                },
            }
            
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("Saved feedback data")
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")

    def record_feedback(
        self,
        query: str,
        chunk_id: UUID,
        helpful: bool,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None,
    ) -> None:
        """Record user feedback for a query-chunk pair."""
        feedback_entry = {
            'chunk_id': str(chunk_id),
            'helpful': helpful,
            'rating': rating,
            'feedback_text': feedback_text,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        self.feedback_data[query].append(feedback_entry)
        
        # Update chunk score
        current_score = self.chunk_scores.get(chunk_id, 0.0)
        
        if helpful:
            # Positive feedback
            score_delta = self.learning_rate * (1.0 if rating is None else rating / 5.0)
        else:
            # Negative feedback
            score_delta = -self.learning_rate * (1.0 if rating is None else (5 - rating) / 5.0)
        
        self.chunk_scores[chunk_id] = current_score + score_delta
        
        logger.info(f"Recorded feedback for query='{query}', chunk={chunk_id}, helpful={helpful}")
        
        # Save to disk
        self._save_feedback()

    def get_chunk_feedback_score(self, chunk_id: UUID) -> float:
        """Get accumulated feedback score for a chunk."""
        return self.chunk_scores.get(chunk_id, 0.0)

    def apply_feedback_to_scores(
        self,
        results: list[tuple],  # List of (chunk, score) or similar
    ) -> list[tuple]:
        """Apply feedback scores to search results."""
        adjusted_results = []
        
        for item in results:
            # Handle different tuple structures
            if len(item) >= 2:
                chunk = item[0]
                original_score = item[1]
                
                # Get feedback score
                feedback_score = self.get_chunk_feedback_score(chunk.id)
                
                # Apply feedback with learning rate
                adjusted_score = original_score + feedback_score
                
                # Reconstruct tuple with adjusted score
                if len(item) == 2:
                    adjusted_results.append((chunk, adjusted_score))
                else:
                    # Preserve additional elements
                    adjusted_results.append((chunk, adjusted_score) + item[2:])
            else:
                adjusted_results.append(item)
        
        # Re-sort by adjusted score
        adjusted_results.sort(key=lambda x: x[1], reverse=True)
        
        return adjusted_results

    def get_query_history(self, query: str, limit: int = 10) -> list[dict]:
        """Get feedback history for a query."""
        feedback = self.feedback_data.get(query, [])
        return feedback[-limit:]

    def get_statistics(self) -> dict:
        """Get feedback statistics."""
        total_feedback = sum(len(fb) for fb in self.feedback_data.values())
        helpful_count = sum(
            1 for fb_list in self.feedback_data.values()
            for fb in fb_list if fb['helpful']
        )
        
        avg_rating = 0.0
        rating_count = 0
        for fb_list in self.feedback_data.values():
            for fb in fb_list:
                if fb['rating'] is not None:
                    avg_rating += fb['rating']
                    rating_count += 1
        
        if rating_count > 0:
            avg_rating /= rating_count
        
        return {
            'total_queries': len(self.feedback_data),
            'total_feedback': total_feedback,
            'helpful_count': helpful_count,
            'helpful_rate': helpful_count / total_feedback if total_feedback > 0 else 0,
            'average_rating': avg_rating,
            'chunks_with_feedback': len(self.chunk_scores),
        }

    def get_top_chunks(self, limit: int = 10) -> list[tuple[UUID, float]]:
        """Get top-rated chunks based on feedback."""
        sorted_chunks = sorted(
            self.chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_chunks[:limit]

    def get_bottom_chunks(self, limit: int = 10) -> list[tuple[UUID, float]]:
        """Get lowest-rated chunks based on feedback."""
        sorted_chunks = sorted(
            self.chunk_scores.items(),
            key=lambda x: x[1]
        )
        return sorted_chunks[:limit]
