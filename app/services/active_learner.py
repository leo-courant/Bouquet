"""Active learning service for improving system from feedback."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


class ActiveLearner:
    """Service for learning from user feedback and improving retrieval."""

    def __init__(
        self,
        feedback_file: str = "data/feedback.json",
        learning_rate: float = 0.01,
        model_file: str = "data/learned_weights.json",
    ) -> None:
        """Initialize active learner."""
        self.feedback_file = Path(feedback_file)
        self.model_file = Path(model_file)
        self.learning_rate = learning_rate
        
        # Learned parameters
        self.strategy_performance = defaultdict(lambda: {'count': 0, 'avg_rating': 3.0})
        self.entity_relevance = defaultdict(lambda: {'count': 0, 'avg_rating': 3.0})
        self.query_pattern_performance = defaultdict(lambda: {'count': 0, 'avg_rating': 3.0})
        
        self._load_model()
        logger.info("Initialized ActiveLearner")

    def _load_model(self) -> None:
        """Load learned model from disk."""
        if self.model_file.exists():
            try:
                with open(self.model_file, 'r') as f:
                    data = json.load(f)
                    self.strategy_performance = defaultdict(
                        lambda: {'count': 0, 'avg_rating': 3.0},
                        data.get('strategy_performance', {})
                    )
                    self.entity_relevance = defaultdict(
                        lambda: {'count': 0, 'avg_rating': 3.0},
                        data.get('entity_relevance', {})
                    )
                    self.query_pattern_performance = defaultdict(
                        lambda: {'count': 0, 'avg_rating': 3.0},
                        data.get('query_pattern_performance', {})
                    )
                logger.info("Loaded learned model from disk")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

    def _save_model(self) -> None:
        """Save learned model to disk."""
        try:
            self.model_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_file, 'w') as f:
                json.dump({
                    'strategy_performance': dict(self.strategy_performance),
                    'entity_relevance': dict(self.entity_relevance),
                    'query_pattern_performance': dict(self.query_pattern_performance),
                    'last_updated': datetime.utcnow().isoformat(),
                }, f, indent=2)
            logger.debug("Saved learned model to disk")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def update_from_feedback(
        self,
        query: str,
        strategy: str,
        entities: list[str],
        rating: int,
        helpful: bool,
    ) -> None:
        """Update learned parameters from user feedback."""
        
        # Normalize rating to 1-5 scale
        rating = max(1, min(5, rating))
        
        # Update strategy performance
        strategy_stats = self.strategy_performance[strategy]
        strategy_stats['avg_rating'] = self._exponential_moving_average(
            strategy_stats['avg_rating'],
            rating,
            strategy_stats['count'],
        )
        strategy_stats['count'] += 1
        
        # Update entity relevance
        for entity in entities:
            entity_stats = self.entity_relevance[entity]
            entity_stats['avg_rating'] = self._exponential_moving_average(
                entity_stats['avg_rating'],
                rating,
                entity_stats['count'],
            )
            entity_stats['count'] += 1
        
        # Update query pattern performance
        query_pattern = self._extract_query_pattern(query)
        pattern_stats = self.query_pattern_performance[query_pattern]
        pattern_stats['avg_rating'] = self._exponential_moving_average(
            pattern_stats['avg_rating'],
            rating,
            pattern_stats['count'],
        )
        pattern_stats['count'] += 1
        
        # Save model periodically
        if sum(s['count'] for s in self.strategy_performance.values()) % 10 == 0:
            self._save_model()
        
        logger.info(f"Updated model from feedback: rating={rating}, strategy={strategy}")

    def _exponential_moving_average(
        self,
        current_avg: float,
        new_value: float,
        count: int,
    ) -> float:
        """Compute exponential moving average with learning rate."""
        # Use learning rate for recent feedback, but consider count
        effective_lr = self.learning_rate * (1.0 + 1.0 / max(count, 1))
        effective_lr = min(effective_lr, 0.3)  # Cap at 30%
        
        return current_avg * (1 - effective_lr) + new_value * effective_lr

    def _extract_query_pattern(self, query: str) -> str:
        """Extract pattern from query for generalization."""
        query_lower = query.lower()
        
        # Simple pattern extraction based on question words
        patterns = {
            'what_is': ['what is', 'what are', 'what was'],
            'how_to': ['how to', 'how do', 'how can'],
            'why': ['why', 'what causes', 'what makes'],
            'when': ['when', 'what year', 'what date'],
            'where': ['where', 'in which', 'at which'],
            'who': ['who', 'which person', 'which people'],
            'compare': ['compare', 'difference between', 'vs', 'versus'],
            'list': ['list', 'what are all', 'enumerate'],
        }
        
        for pattern_name, keywords in patterns.items():
            if any(kw in query_lower for kw in keywords):
                return pattern_name
        
        return 'general'

    def recommend_strategy(self, query: str, entities: list[str]) -> Optional[str]:
        """Recommend retrieval strategy based on learned patterns."""
        
        query_pattern = self._extract_query_pattern(query)
        
        # Get pattern-specific best strategy
        pattern_stats = self.query_pattern_performance[query_pattern]
        
        if pattern_stats['count'] < 5:
            # Not enough data, no recommendation
            return None
        
        # Find best performing strategy for this pattern
        best_strategy = None
        best_score = 0.0
        
        for strategy, stats in self.strategy_performance.items():
            if stats['count'] > 0:
                # Weight by performance and confidence
                confidence = min(1.0, stats['count'] / 10.0)
                score = stats['avg_rating'] * confidence
                
                if score > best_score:
                    best_score = score
                    best_strategy = strategy
        
        if best_strategy and best_score >= 3.5:
            logger.info(f"Recommending strategy '{best_strategy}' for pattern '{query_pattern}'")
            return best_strategy
        
        return None

    def get_entity_boost(self, entity: str) -> float:
        """Get learned boost factor for an entity."""
        stats = self.entity_relevance.get(entity)
        
        if not stats or stats['count'] < 3:
            return 1.0  # Neutral boost
        
        # Convert rating (1-5) to boost factor (0.7-1.3)
        normalized_rating = (stats['avg_rating'] - 3.0) / 2.0  # -1 to 1
        boost = 1.0 + normalized_rating * 0.3
        
        return max(0.7, min(1.3, boost))

    def get_performance_report(self) -> dict:
        """Get performance report for all learned patterns."""
        
        report = {
            'strategies': {},
            'entities': {},
            'query_patterns': {},
            'total_feedback_count': 0,
        }
        
        # Strategy performance
        for strategy, stats in self.strategy_performance.items():
            if stats['count'] > 0:
                report['strategies'][strategy] = {
                    'avg_rating': round(stats['avg_rating'], 2),
                    'count': stats['count'],
                    'performance': 'excellent' if stats['avg_rating'] >= 4.0
                                   else 'good' if stats['avg_rating'] >= 3.5
                                   else 'average' if stats['avg_rating'] >= 3.0
                                   else 'poor',
                }
                report['total_feedback_count'] += stats['count']
        
        # Top entities
        sorted_entities = sorted(
            self.entity_relevance.items(),
            key=lambda x: (x[1]['avg_rating'], x[1]['count']),
            reverse=True
        )
        
        for entity, stats in sorted_entities[:20]:  # Top 20
            if stats['count'] >= 3:
                report['entities'][entity] = {
                    'avg_rating': round(stats['avg_rating'], 2),
                    'count': stats['count'],
                }
        
        # Query patterns
        for pattern, stats in self.query_pattern_performance.items():
            if stats['count'] > 0:
                report['query_patterns'][pattern] = {
                    'avg_rating': round(stats['avg_rating'], 2),
                    'count': stats['count'],
                }
        
        return report

    def should_trigger_retraining(self) -> bool:
        """Determine if model should be retrained based on feedback volume."""
        total_feedback = sum(s['count'] for s in self.strategy_performance.values())
        
        # Trigger retraining every 100 feedback items
        return total_feedback > 0 and total_feedback % 100 == 0

    def reset_model(self) -> None:
        """Reset learned model (for testing or manual reset)."""
        self.strategy_performance.clear()
        self.entity_relevance.clear()
        self.query_pattern_performance.clear()
        
        if self.model_file.exists():
            self.model_file.unlink()
        
        logger.info("Reset learned model")
