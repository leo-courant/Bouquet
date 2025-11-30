"""Neo4j database repository for graph operations."""

import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable
from neo4j.time import DateTime as Neo4jDateTime

from app.domain import (
    Chunk,
    Community,
    Document,
    Entity,
    GraphEdge,
    GraphNode,
    GraphStats,
    Relationship,
)


def neo4j_datetime_to_python(dt: Any) -> datetime:
    """Convert Neo4j DateTime to Python datetime."""
    if isinstance(dt, Neo4jDateTime):
        return dt.to_native()
    return dt


class Neo4jRepository:
    """Repository for Neo4j graph database operations."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        """Initialize Neo4j repository."""
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        try:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            await self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            await self._create_indexes()
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            logger.info("Closed Neo4j connection")

    async def _create_indexes(self) -> None:
        """Create necessary indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.id)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.id)",
            "CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.level)",
        ]

        async with self._driver.session(database=self.database) as session:
            for index in indexes:
                await session.run(index)
        logger.info("Created database indexes")

    # Document Operations
    async def create_document(self, document: Document) -> Document:
        """Create a new document node."""
        # Build query conditionally based on metadata
        if document.metadata and len(document.metadata) > 0:
            query = """
            CREATE (d:Document {
                id: $id,
                title: $title,
                content: $content,
                source: $source,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at),
                metadata: $metadata
            })
            RETURN d
            """
            params = {
                "id": str(document.id),
                "title": document.title,
                "content": document.content,
                "source": document.source,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "metadata": json.dumps(document.metadata),  # Convert to JSON string
            }
        else:
            query = """
            CREATE (d:Document {
                id: $id,
                title: $title,
                content: $content,
                source: $source,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at)
            })
            RETURN d
            """
            params = {
                "id": str(document.id),
                "title": document.title,
                "content": document.content,
                "source": document.source,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            }

        async with self._driver.session(database=self.database) as session:
            await session.run(query, params)
            logger.info(f"Created document: {document.id}")
            return document

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get a document by ID."""
        query = """
        MATCH (d:Document {id: $id})
        RETURN d
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"id": str(document_id)})
            record = await result.single()
            if record:
                node = record["d"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                return Document(
                    id=UUID(node["id"]),
                    title=node["title"],
                    content=node["content"],
                    source=node.get("source"),
                    metadata=metadata,
                    created_at=neo4j_datetime_to_python(node["created_at"]),
                    updated_at=neo4j_datetime_to_python(node["updated_at"]),
                )
            return None

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete a document and all associated nodes."""
        query = """
        MATCH (d:Document {id: $id})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        OPTIONAL MATCH (c)-[:CONTAINS_ENTITY]->(e:Entity)
        DETACH DELETE d, c, e
        RETURN count(d) as deleted
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"id": str(document_id)})
            record = await result.single()
            deleted = record["deleted"] > 0
            if deleted:
                logger.info(f"Deleted document: {document_id}")
            return deleted

    # Chunk Operations
    async def create_chunk(self, chunk: Chunk) -> Chunk:
        """Create a new chunk node and link to document."""
        # Build query conditionally based on metadata
        if chunk.metadata and len(chunk.metadata) > 0:
            query = """
            MATCH (d:Document {id: $document_id})
            CREATE (c:Chunk {
                id: $id,
                content: $content,
                chunk_index: $chunk_index,
                start_char: $start_char,
                end_char: $end_char,
                created_at: datetime($created_at),
                metadata: $metadata
            })
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN c
            """
            params = {
                "id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "created_at": chunk.created_at.isoformat(),
                "metadata": json.dumps(chunk.metadata),  # Convert to JSON string
            }
        else:
            query = """
            MATCH (d:Document {id: $document_id})
            CREATE (c:Chunk {
                id: $id,
                content: $content,
                chunk_index: $chunk_index,
                start_char: $start_char,
                end_char: $end_char,
                created_at: datetime($created_at)
            })
            CREATE (d)-[:HAS_CHUNK]->(c)
            RETURN c
            """
            params = {
                "id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "created_at": chunk.created_at.isoformat(),
            }

        async with self._driver.session(database=self.database) as session:
            await session.run(query, params)
            logger.debug(f"Created chunk: {chunk.id}")
            return chunk

    async def set_chunk_embedding(self, chunk_id: UUID, embedding: list[float]) -> None:
        """Set embedding vector for a chunk."""
        query = """
        MATCH (c:Chunk {id: $id})
        SET c.embedding = $embedding
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(query, {"id": str(chunk_id), "embedding": embedding})

    async def get_chunk(self, chunk_id: UUID) -> Optional[Chunk]:
        """Get a chunk by ID."""
        query = """
        MATCH (c:Chunk {id: $id})
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        RETURN c, d.id as document_id
        """
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"id": str(chunk_id)})
            record = await result.single()
            if record:
                node = record["c"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                return Chunk(
                    id=UUID(node["id"]),
                    document_id=UUID(record["document_id"]),
                    content=node["content"],
                    embedding=node.get("embedding"),
                    chunk_index=node["chunk_index"],
                    start_char=node["start_char"],
                    end_char=node["end_char"],
                    metadata=metadata,
                    created_at=neo4j_datetime_to_python(node["created_at"]),
                )
            return None

    # Entity Operations
    async def create_entity(self, entity: Entity) -> Entity:
        """Create or merge an entity node."""
        # Build query conditionally based on metadata
        if entity.metadata and len(entity.metadata) > 0:
            query = """
            MERGE (e:Entity {name: $name, entity_type: $entity_type})
            ON CREATE SET 
                e.id = $id,
                e.description = $description,
                e.metadata = $metadata
            ON MATCH SET
                e.description = COALESCE($description, e.description),
                e.metadata = COALESCE($metadata, e.metadata)
            RETURN e
            """
            params = {
                "id": str(entity.id),
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "metadata": json.dumps(entity.metadata),  # Convert to JSON string
            }
        else:
            query = """
            MERGE (e:Entity {name: $name, entity_type: $entity_type})
            ON CREATE SET 
                e.id = $id,
                e.description = $description
            ON MATCH SET
                e.description = COALESCE($description, e.description)
            RETURN e
            """
            params = {
                "id": str(entity.id),
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
            }

        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, params)
            record = await result.single()
            node = record["e"]
            metadata_str = node.get("metadata", "{}")
            metadata = json.loads(metadata_str) if metadata_str else {}
            logger.debug(f"Created/merged entity: {entity.name}")
            return Entity(
                id=UUID(node["id"]),
                name=node["name"],
                entity_type=node["entity_type"],
                description=node.get("description"),
                metadata=metadata,
            )

    async def link_chunk_to_entity(self, chunk_id: UUID, entity_id: UUID) -> None:
        """Create relationship between chunk and entity."""
        query = """
        MATCH (c:Chunk {id: $chunk_id})
        MATCH (e:Entity {id: $entity_id})
        MERGE (c)-[:CONTAINS_ENTITY]->(e)
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(query, {"chunk_id": str(chunk_id), "entity_id": str(entity_id)})

    async def create_relationship(self, relationship: Relationship) -> Relationship:
        """Create a relationship between entities."""
        query = """
        MATCH (source:Entity {id: $source_id})
        MATCH (target:Entity {id: $target_id})
        MERGE (source)-[r:RELATED {type: $rel_type}]->(target)
        ON CREATE SET
            r.id = $id,
            r.description = $description,
            r.weight = $weight,
            r.metadata = $metadata
        ON MATCH SET
            r.weight = r.weight + $weight
        RETURN r
        """
        params = {
            "id": str(relationship.id),
            "source_id": str(relationship.source_entity_id),
            "target_id": str(relationship.target_entity_id),
            "rel_type": relationship.relationship_type,
            "description": relationship.description,
            "weight": relationship.weight,
            "metadata": relationship.metadata,
        }

        async with self._driver.session(database=self.database) as session:
            await session.run(query, params)
            logger.debug(
                f"Created relationship: {relationship.source_entity_id} -> {relationship.target_entity_id}"
            )
            return relationship

    # Community Operations
    async def create_community(self, community: Community) -> Community:
        """Create a community node."""
        query = """
        CREATE (com:Community {
            id: $id,
            level: $level,
            summary: $summary,
            properties: $properties,
            created_at: datetime($created_at)
        })
        RETURN com
        """
        params = {
            "id": str(community.id),
            "level": community.level,
            "summary": community.summary,
            "properties": community.properties,
            "created_at": community.created_at.isoformat(),
        }

        async with self._driver.session(database=self.database) as session:
            await session.run(query, params)

            # Link members to community
            for member_id in community.members:
                await self._link_node_to_community(member_id, community.id)

            # Link parent if exists
            if community.parent_community_id:
                await self._link_communities(community.id, community.parent_community_id)

            logger.info(f"Created community: {community.id} at level {community.level}")
            return community

    async def _link_node_to_community(self, node_id: UUID, community_id: UUID) -> None:
        """Link a node to a community."""
        query = """
        MATCH (n {id: $node_id})
        MATCH (com:Community {id: $community_id})
        MERGE (n)-[:BELONGS_TO]->(com)
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(
                query, {"node_id": str(node_id), "community_id": str(community_id)}
            )

    async def _link_communities(
        self, child_id: UUID, parent_id: UUID
    ) -> None:
        """Link child community to parent."""
        query = """
        MATCH (child:Community {id: $child_id})
        MATCH (parent:Community {id: $parent_id})
        MERGE (child)-[:PART_OF]->(parent)
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(query, {"child_id": str(child_id), "parent_id": str(parent_id)})

    async def set_community_embedding(
        self, community_id: UUID, embedding: list[float]
    ) -> None:
        """Set embedding vector for a community."""
        query = """
        MATCH (com:Community {id: $id})
        SET com.embedding = $embedding
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(query, {"id": str(community_id), "embedding": embedding})

    # Search Operations
    async def search_similar_chunks(
        self, embedding: list[float], top_k: int = 10
    ) -> list[tuple[Chunk, float]]:
        """Search for similar chunks using embedding similarity."""
        query = """
        MATCH (c:Chunk)
        WHERE c.embedding IS NOT NULL
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        WITH c, d, 
             gds.similarity.cosine(c.embedding, $embedding) AS score
        WHERE score > 0.3
        RETURN c, d.id as document_id, score
        ORDER BY score DESC
        LIMIT $top_k
        """
        results = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"embedding": embedding, "top_k": top_k})
            async for record in result:
                node = record["c"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                chunk = Chunk(
                    id=UUID(node["id"]),
                    document_id=UUID(record["document_id"]),
                    content=node["content"],
                    embedding=node.get("embedding"),
                    chunk_index=node["chunk_index"],
                    start_char=node["start_char"],
                    end_char=node["end_char"],
                    metadata=metadata,
                    created_at=neo4j_datetime_to_python(node["created_at"]),
                )
                results.append((chunk, record["score"]))
        return results

    async def get_entities_for_chunk(self, chunk_id: UUID) -> list[Entity]:
        """Get all entities mentioned in a chunk."""
        query = """
        MATCH (c:Chunk {id: $chunk_id})-[:CONTAINS_ENTITY]->(e:Entity)
        RETURN e
        """
        entities = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"chunk_id": str(chunk_id)})
            async for record in result:
                node = record["e"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                entities.append(
                    Entity(
                        id=UUID(node["id"]),
                        name=node["name"],
                        entity_type=node["entity_type"],
                        description=node.get("description"),
                        metadata=metadata,
                    )
                )
        return entities

    # Statistics
    async def get_graph_stats(self) -> GraphStats:
        """Get statistics about the knowledge graph."""
        # Count nodes by label separately
        count_query = """
        MATCH (n)
        WITH labels(n)[0] as label, count(n) as count
        RETURN label, count
        """
        
        # Count edges
        edge_query = """
        MATCH ()-[r]->()
        RETURN count(r) as edge_count
        """
        
        stats = GraphStats()

        async with self._driver.session(database=self.database) as session:
            # Get node counts by type
            result = await session.run(count_query)
            async for record in result:
                label = record["label"]
                count = record["count"]
                if label:  # Skip nodes without labels
                    stats.nodes_by_type[label] = count
                    stats.total_nodes += count
            
            # Get edge count
            result = await session.run(edge_query)
            record = await result.single()
            if record:
                stats.total_edges = record["edge_count"] or 0

            # Calculate metrics
            if stats.total_nodes > 0:
                stats.avg_degree = (2.0 * stats.total_edges) / stats.total_nodes
                max_edges = stats.total_nodes * (stats.total_nodes - 1)
                if max_edges > 0:
                    stats.density = stats.total_edges / max_edges
        
        logger.info(f"Graph stats: {stats.total_nodes} nodes, {stats.total_edges} edges, by type: {stats.nodes_by_type}")
        return stats

    async def clear_all(self) -> None:
        """Clear all data from the database (use with caution!)."""
        query = "MATCH (n) DETACH DELETE n"
        async with self._driver.session(database=self.database) as session:
            await session.run(query)
            logger.warning("Cleared all data from Neo4j")
