"""Query complexity analyzer for intelligent query routing."""

from typing import Optional
from loguru import logger

from app.repositories import Neo4jRepository


class QueryComplexityAnalyzer:
    """Analyzes query complexity and database state to determine optimal query routing."""

    def __init__(
        self,
        repository: Neo4jRepository,
    ) -> None:
        """Initialize query complexity analyzer."""
        self.repository = repository
        self.db_stats_cache = None
        self.db_structure_cache = None
        logger.info("Initialized QueryComplexityAnalyzer")

    async def get_database_overview(self) -> dict:
        """Get a general idea of database structure and complexity."""
        if self.db_structure_cache:
            return self.db_structure_cache
        
        try:
            stats = await self.repository.get_graph_stats()
            
            # Calculate complexity indicators
            total_nodes = stats.total_nodes
            total_edges = stats.total_edges
            
            # Determine database complexity level
            if total_nodes < 10:
                db_complexity = "minimal"
            elif total_nodes < 50:
                db_complexity = "simple"
            elif total_nodes < 200:
                db_complexity = "moderate"
            elif total_nodes < 1000:
                db_complexity = "complex"
            else:
                db_complexity = "very_complex"
            
            # Calculate average connectivity (edges per node)
            avg_connectivity = total_edges / max(total_nodes, 1)
            
            # Determine if database has rich semantic relationships
            has_rich_semantics = avg_connectivity > 2.0
            
            self.db_structure_cache = {
                'total_nodes': total_nodes,
                'total_edges': total_edges,
                'avg_connectivity': avg_connectivity,
                'db_complexity': db_complexity,
                'has_rich_semantics': has_rich_semantics,
                'node_types': stats.nodes_by_type,
            }
            
            logger.info(
                f"Database overview: {total_nodes} nodes, {total_edges} edges, "
                f"complexity={db_complexity}, avg_connectivity={avg_connectivity:.2f}"
            )
            
            return self.db_structure_cache
            
        except Exception as e:
            logger.warning(f"Failed to get database overview: {e}")
            return {
                'total_nodes': 0,
                'total_edges': 0,
                'avg_connectivity': 0.0,
                'db_complexity': "unknown",
                'has_rich_semantics': False,
                'node_types': {},
            }

    def analyze_query_complexity(self, query: str, entities: Optional[list[str]] = None) -> dict:
        """Analyze the intrinsic complexity of a query."""
        query_lower = query.strip().lower()
        words = query_lower.split()
        
        # Calculate query length complexity
        if len(words) <= 5:
            length_complexity = "simple"
        elif len(words) <= 10:
            length_complexity = "moderate"
        elif len(words) <= 20:
            length_complexity = "complex"
        else:
            length_complexity = "very_complex"
        
        # Check for complexity indicators
        complexity_indicators = {
            'comparison': any(word in query_lower for word in [
                'compare', 'difference', 'versus', 'vs', 'between', 'contrast', 'similar', 'different'
            ]),
            'aggregation': any(word in query_lower for word in [
                'all', 'every', 'each', 'total', 'sum', 'count', 'how many', 'list'
            ]),
            'reasoning': any(word in query_lower for word in [
                'why', 'how', 'explain', 'analyze', 'evaluate', 'assess', 'determine'
            ]),
            'temporal': any(word in query_lower for word in [
                'when', 'before', 'after', 'during', 'recent', 'latest', 'first', 'last'
            ]),
            'multi_entity': entities and len(entities) > 2 if entities else False,
            'nested': any(word in query_lower for word in [
                'related to', 'connected to', 'associated with', 'linked to'
            ]),
        }
        
        # Count active complexity indicators
        complexity_score = sum(complexity_indicators.values())
        
        # Determine overall query complexity
        if complexity_score == 0:
            query_complexity = "simple"
        elif complexity_score <= 1:
            query_complexity = "moderate"
        elif complexity_score <= 2:
            query_complexity = "complex"
        else:
            query_complexity = "very_complex"
        
        return {
            'query_complexity': query_complexity,
            'length_complexity': length_complexity,
            'complexity_score': complexity_score,
            'indicators': complexity_indicators,
            'word_count': len(words),
        }

    async def should_use_ultra_advanced(
        self,
        query: str,
        entities: Optional[list[str]] = None,
        initial_retrieval_quality: Optional[float] = None,
    ) -> dict:
        """
        Determine if ultra-advanced query processing is needed.
        
        Args:
            query: The user query
            entities: Extracted entities from query
            initial_retrieval_quality: Average score of initial retrieval (0-1)
            
        Returns:
            Dict with decision and reasoning
        """
        # Get database overview
        db_overview = await self.get_database_overview()
        
        # Analyze query complexity
        query_analysis = self.analyze_query_complexity(query, entities)
        
        # Decision factors
        factors = {
            'use_ultra': False,
            'reasoning': [],
            'confidence': 0.0,
        }
        
        # Factor 1: Database is very simple (< 10 nodes)
        if db_overview['total_nodes'] < 10:
            factors['reasoning'].append("Database is minimal - simple search sufficient")
            factors['use_ultra'] = False
            factors['confidence'] = 0.9
            return factors
        
        # Factor 2: Query is very simple and database is simple
        if query_analysis['query_complexity'] == "simple" and db_overview['db_complexity'] in ['minimal', 'simple']:
            if not query_analysis['indicators']['reasoning'] and not query_analysis['indicators']['comparison']:
                factors['reasoning'].append("Simple query on simple database - basic retrieval sufficient")
                factors['use_ultra'] = False
                factors['confidence'] = 0.85
                return factors
        
        # Factor 3: Initial retrieval quality is very high
        if initial_retrieval_quality is not None and initial_retrieval_quality >= 0.9:
            factors['reasoning'].append("Initial retrieval quality is excellent")
            factors['use_ultra'] = False
            factors['confidence'] = 0.8
            return factors
        
        # Factor 4: Complex query indicators present
        if query_analysis['complexity_score'] >= 2:
            factors['reasoning'].append(f"Complex query detected (score={query_analysis['complexity_score']})")
            factors['use_ultra'] = True
            factors['confidence'] = 0.85
            return factors
        
        # Factor 5: Database has rich semantics and query involves relationships
        if db_overview['has_rich_semantics'] and query_analysis['indicators']['nested']:
            factors['reasoning'].append("Rich semantic database with relationship query")
            factors['use_ultra'] = True
            factors['confidence'] = 0.8
            return factors
        
        # Factor 6: Initial retrieval quality is poor
        if initial_retrieval_quality is not None and initial_retrieval_quality < 0.6:
            factors['reasoning'].append("Initial retrieval quality is low - need advanced processing")
            factors['use_ultra'] = True
            factors['confidence'] = 0.75
            return factors
        
        # Factor 7: Database is moderate/complex and query is not trivial
        if db_overview['db_complexity'] in ['moderate', 'complex', 'very_complex']:
            if query_analysis['query_complexity'] in ['moderate', 'complex', 'very_complex']:
                factors['reasoning'].append("Moderate/complex database with non-trivial query")
                factors['use_ultra'] = True
                factors['confidence'] = 0.7
                return factors
        
        # Default: Use advanced for safety but with low confidence
        factors['reasoning'].append("Default to advanced processing for safety")
        factors['use_ultra'] = True
        factors['confidence'] = 0.5
        
        return factors

    async def recommend_strategy(
        self,
        query: str,
        entities: Optional[list[str]] = None,
    ) -> str:
        """Recommend specific retrieval strategy based on query and database."""
        db_overview = await self.get_database_overview()
        query_analysis = self.analyze_query_complexity(query, entities)
        
        # Very simple cases - use vector only
        if db_overview['total_nodes'] < 5:
            return "vector_only"
        
        # Entity-heavy queries with entities
        if entities and len(entities) > 0:
            return "entity_aware"
        
        # Relationship queries on connected graph
        if query_analysis['indicators']['nested'] and db_overview['avg_connectivity'] > 1.5:
            return "graph_traversal"
        
        # Comparison queries
        if query_analysis['indicators']['comparison']:
            return "hybrid"
        
        # Broad exploratory queries
        if any(word in query.lower() for word in ['overview', 'summary', 'tell me about', 'what is']):
            if db_overview['db_complexity'] in ['simple', 'minimal']:
                return "vector_only"
            else:
                return "community_based"
        
        # Default to hybrid for balanced performance
        return "hybrid"

    def invalidate_cache(self) -> None:
        """Invalidate cached database statistics (call after ingestion)."""
        self.db_stats_cache = None
        self.db_structure_cache = None
        logger.info("Invalidated database structure cache")
