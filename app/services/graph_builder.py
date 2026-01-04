"""Graph builder service for constructing hierarchical knowledge graphs."""

from typing import Optional
from uuid import UUID

import community as community_louvain
import networkx as nx
from loguru import logger

from app.domain import Community
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService


class GraphBuilder:
    """Service for building hierarchical graph-of-graphs structure."""

    def __init__(
        self,
        repository: Neo4jRepository,
        min_community_size: int = 3,
        max_levels: int = 3,
        similarity_threshold: float = 0.7,
    ) -> None:
        """Initialize graph builder."""
        logger.debug(f"[DEBUG] GraphBuilder.__init__ called with min_size={min_community_size}, max_levels={max_levels}, threshold={similarity_threshold}")
        try:
            self.repository = repository
            self.min_community_size = min_community_size
            self.max_levels = max_levels
            self.similarity_threshold = similarity_threshold
            logger.info(
                f"Initialized GraphBuilder (min_size={min_community_size}, max_levels={max_levels})"
            )
            logger.debug(f"[DEBUG] GraphBuilder initialized successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize GraphBuilder: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] GraphBuilder.__init__ traceback:")
            raise

    async def build_entity_graph(self) -> nx.Graph:
        """Build NetworkX graph from Neo4j entity relationships."""
        logger.debug(f"[DEBUG] build_entity_graph called")
        try:
            query = """
            MATCH (e1:Entity)-[r:RELATED]->(e2:Entity)
            RETURN e1.id as source, e2.id as target, r.weight as weight
            """

            G = nx.Graph()
            logger.debug(f"[DEBUG] Executing Neo4j query to fetch entity relationships")

            async with self.repository._driver.session(
                database=self.repository.database
            ) as session:
                result = await session.run(query)
                edge_count = 0
                async for record in result:
                    G.add_edge(
                        record["source"],
                        record["target"],
                        weight=record.get("weight", 1.0),
                    )
                    edge_count += 1
                    if edge_count % 100 == 0:
                        logger.debug(f"[DEBUG] Processed {edge_count} edges")

            logger.info(f"Built entity graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            logger.debug(f"[DEBUG] build_entity_graph completed successfully")
            return G
        except Exception as e:
            logger.error(f"[ERROR] Failed to build entity graph: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] Entity graph building error:")
            raise

    def detect_communities(self, graph: nx.Graph, resolution: float = 1.0) -> dict[str, int]:
        """Detect communities using Louvain algorithm."""
        if graph.number_of_nodes() == 0:
            return {}

        partition = community_louvain.best_partition(graph, resolution=resolution)
        logger.info(f"Detected {len(set(partition.values()))} communities")
        return partition

    async def build_hierarchical_communities(
        self, embedding_service: Optional[EmbeddingService] = None
    ) -> list[list[Community]]:
        """Build hierarchical communities from entity graph."""
        logger.info("Building hierarchical community structure")

        all_levels: list[list[Community]] = []

        # Level 0: Build initial entity graph
        graph = await self.build_entity_graph()

        if graph.number_of_nodes() == 0:
            logger.warning("No entities found in graph")
            return all_levels

        current_level = 0
        current_graph = graph

        while current_level < self.max_levels and current_graph.number_of_nodes() > 1:
            # Detect communities at this level
            partition = self.detect_communities(current_graph, resolution=1.0 + current_level * 0.5)

            # Group nodes by community
            communities_dict: dict[int, list[str]] = {}
            for node, comm_id in partition.items():
                if comm_id not in communities_dict:
                    communities_dict[comm_id] = []
                communities_dict[comm_id].append(node)

            # Create community objects
            level_communities = []
            for comm_id, members in communities_dict.items():
                if len(members) >= self.min_community_size or current_level == 0:
                    # Get entity names for summary
                    member_uuids = [UUID(m) for m in members]

                    # Create summary
                    summary = await self._generate_community_summary(member_uuids)

                    community = Community(
                        level=current_level,
                        members=member_uuids,
                        summary=summary,
                    )

                    # Save to Neo4j
                    await self.repository.create_community(community)

                    # Generate embedding for community if service provided
                    if embedding_service and summary:
                        embedding = await embedding_service.generate_embedding(summary)
                        await self.repository.set_community_embedding(community.id, embedding)

                    level_communities.append(community)

            all_levels.append(level_communities)
            logger.info(f"Level {current_level}: Created {len(level_communities)} communities")

            # Build next level graph from communities
            if len(level_communities) <= 1:
                break

            next_graph = nx.Graph()
            for i, comm1 in enumerate(level_communities):
                for j, comm2 in enumerate(level_communities):
                    if i < j:
                        # Calculate edge weight based on shared members or connections
                        weight = self._calculate_community_similarity(
                            comm1, comm2, current_graph
                        )
                        if weight > 0:
                            next_graph.add_edge(str(comm1.id), str(comm2.id), weight=weight)

            current_graph = next_graph
            current_level += 1

        logger.info(f"Built {len(all_levels)} hierarchical levels")
        return all_levels

    async def _generate_community_summary(self, member_ids: list[UUID]) -> str:
        """Generate a summary for a community based on its members."""
        # Get entity names from Neo4j
        query = """
        MATCH (e:Entity)
        WHERE e.id IN $ids
        RETURN e.name as name, e.entity_type as type
        LIMIT 10
        """

        entity_names = []
        async with self.repository._driver.session(
            database=self.repository.database
        ) as session:
            result = await session.run(query, {"ids": [str(id) for id in member_ids]})
            async for record in result:
                entity_names.append(f"{record['name']} ({record['type']})")

        if entity_names:
            summary = f"Community of {len(member_ids)} entities including: {', '.join(entity_names[:5])}"
            if len(entity_names) > 5:
                summary += f" and {len(entity_names) - 5} more"
        else:
            summary = f"Community of {len(member_ids)} entities"

        return summary

    def _calculate_community_similarity(
        self, comm1: Community, comm2: Community, graph: nx.Graph
    ) -> float:
        """Calculate similarity between two communities."""
        # Count connections between members of the two communities
        connections = 0
        total_possible = 0

        for m1 in comm1.members:
            for m2 in comm2.members:
                total_possible += 1
                if graph.has_edge(str(m1), str(m2)):
                    connections += graph[str(m1)][str(m2)].get("weight", 1.0)

        if total_possible == 0:
            return 0.0

        # Normalize by total possible connections
        similarity = connections / total_possible
        return similarity if similarity > 0.1 else 0.0

    async def rebuild_graph(self, embedding_service: EmbeddingService) -> dict:
        """Rebuild the entire hierarchical graph structure."""
        logger.info("Rebuilding hierarchical graph")

        # Clear existing communities
        query = "MATCH (c:Community) DETACH DELETE c"
        async with self.repository._driver.session(
            database=self.repository.database
        ) as session:
            await session.run(query)

        # Build new hierarchy
        levels = await self.build_hierarchical_communities(embedding_service)

        return {
            "total_levels": len(levels),
            "communities_per_level": [len(level) for level in levels],
            "total_communities": sum(len(level) for level in levels),
        }
