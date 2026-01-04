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
        logger.debug(f"[DEBUG] Neo4jRepository.__init__ called: uri={uri}, user={user}, database={database}")
        try:
            self.uri = uri
            self.user = user
            self.password = password
            self.database = database
            self._driver: Optional[AsyncDriver] = None
            logger.debug(f"[DEBUG] Neo4jRepository initialized (connection not yet established)")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Neo4jRepository: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] Neo4jRepository.__init__ traceback:")
            raise

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        logger.debug(f"[DEBUG] Attempting to connect to Neo4j at {self.uri}")
        try:
            logger.debug(f"[DEBUG] Creating AsyncGraphDatabase driver")
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            logger.debug(f"[DEBUG] Verifying Neo4j connectivity")
            await self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            logger.debug(f"[DEBUG] Creating indexes")
            await self._create_indexes()
            logger.debug(f"[DEBUG] Neo4j connection established successfully")
        except ServiceUnavailable as e:
            logger.error(f"[ERROR] Neo4j service unavailable at {self.uri}: {str(e)}")
            logger.error(f"[ERROR] Check if Neo4j is running and accessible")
            logger.exception(f"[EXCEPTION] Neo4j connection error:")
            raise
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to Neo4j at {self.uri}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] Neo4j connection error:")
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
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name)",
            "CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.id)",
            "CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.level)",
            "CREATE FULLTEXT INDEX chunk_content_fulltext IF NOT EXISTS FOR (c:Chunk) ON EACH [c.content]",
            "CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.canonical_name]",
        ]

        async with self._driver.session(database=self.database) as session:
            for index in indexes:
                try:
                    await session.run(index)
                except Exception as e:
                    logger.warning(f"Index creation skipped or failed: {e}")
        logger.info("Created database indexes")

    async def create_vector_index(
        self,
        embedding_dimension: int = 1536,  # Neo4j 5.x limit is 2048
        similarity_function: str = "cosine",
    ) -> None:
        """Create HNSW vector index for chunks using procedure (Neo4j 5.x)."""
        try:
            async with self._driver.session(database=self.database) as session:
                # Check if index already exists
                check_query = "SHOW INDEXES YIELD name, type WHERE name = 'chunk_embedding_index' AND type = 'VECTOR' RETURN name"
                result = await session.run(check_query)
                records = await result.data()
                
                if not records:
                    # Use procedure to create vector index (Neo4j 5.x approach)
                    # Note: Parameters don't work well with procedures, use f-string
                    logger.info(f"Creating vector index with dimension={embedding_dimension}, similarity={similarity_function}")
                    create_query = f"""
                    CALL db.index.vector.createNodeIndex(
                        'chunk_embedding_index',
                        'Chunk',
                        'embedding',
                        {embedding_dimension},
                        '{similarity_function}'
                    )
                    """
                    logger.debug(f"Vector index query: {create_query}")
                    await session.run(create_query)
                    logger.info(f"Created HNSW vector index (dim={embedding_dimension}, sim={similarity_function})")
                else:
                    logger.info("Vector index already exists")
        except Exception as e:
            logger.warning(f"Vector index creation failed: {e}")

    async def create_community_vector_index(
        self,
        embedding_dimension: int = 1536,  # Neo4j 5.x limit is 2048
        similarity_function: str = "cosine",
    ) -> None:
        """Create HNSW vector index for communities using procedure (Neo4j 5.x)."""
        try:
            async with self._driver.session(database=self.database) as session:
                # Check if index already exists
                check_query = "SHOW INDEXES YIELD name, type WHERE name = 'community_embedding_index' AND type = 'VECTOR' RETURN name"
                result = await session.run(check_query)
                records = await result.data()
                
                if not records:
                    # Use procedure to create vector index (Neo4j 5.x approach)
                    # Note: Parameters don't work well with procedures, use f-string
                    create_query = f"""
                    CALL db.index.vector.createNodeIndex(
                        'community_embedding_index',
                        'Community',
                        'embedding',
                        {embedding_dimension},
                        '{similarity_function}'
                    )
                    """
                    await session.run(create_query)
                    logger.info("Created community HNSW vector index")
                else:
                    logger.info("Community vector index already exists")
        except Exception as e:
            logger.warning(f"Community vector index creation failed: {e}")

    # Document Operations
    async def create_document(self, document: Document) -> Document:
        """Create a new document node."""
        logger.debug(f"[DEBUG] create_document called: document_id={document.id}, title={document.title}")
        try:
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

            logger.debug(f"[DEBUG] Executing Neo4j query to create document")
            async with self._driver.session(database=self.database) as session:
                await session.run(query, params)
                logger.info(f"Created document: {document.id}")
                logger.debug(f"[DEBUG] Document created successfully in Neo4j")
                return document
        except Exception as e:
            logger.error(f"[ERROR] Failed to create document {document.id}: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Document details: title={document.title}, content_length={len(document.content)}")
            logger.exception(f"[EXCEPTION] Document creation error:")
            raise

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
        logger.debug(f"[DEBUG] create_chunk called: chunk_id={chunk.id}, document_id={chunk.document_id}, index={chunk.chunk_index}")
        try:
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

            logger.debug(f"[DEBUG] Executing Neo4j query to create chunk")
            async with self._driver.session(database=self.database) as session:
                await session.run(query, params)
                logger.debug(f"Created chunk: {chunk.id}")
                logger.debug(f"[DEBUG] Chunk created successfully in Neo4j")
                return chunk
        except Exception as e:
            logger.error(f"[ERROR] Failed to create chunk {chunk.id}: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Chunk details: document_id={chunk.document_id}, index={chunk.chunk_index}, content_length={len(chunk.content)}")
            logger.exception(f"[EXCEPTION] Chunk creation error:")
            raise

    async def set_chunk_embedding(self, chunk_id: UUID, embedding: list[float]) -> None:
        """Set embedding vector for a chunk."""
        logger.debug(f"[DEBUG] set_chunk_embedding called: chunk_id={chunk_id}, embedding_dim={len(embedding)}")
        try:
            query = """
            MATCH (c:Chunk {id: $id})
            SET c.embedding = $embedding
            """
            logger.debug(f"[DEBUG] Executing Neo4j query to set embedding")
            async with self._driver.session(database=self.database) as session:
                await session.run(query, {"id": str(chunk_id), "embedding": embedding})
                logger.debug(f"[DEBUG] Embedding set successfully for chunk {chunk_id}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to set embedding for chunk {chunk_id}: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Embedding dimension: {len(embedding)}")
            logger.exception(f"[EXCEPTION] Set embedding error:")
            raise

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
        logger.debug(f"[DEBUG] create_entity called: name={entity.name}, type={entity.entity_type}, id={entity.id}")
        try:
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

            logger.debug(f"[DEBUG] Executing Neo4j query to create/merge entity")
            async with self._driver.session(database=self.database) as session:
                result = await session.run(query, params)
                record = await result.single()
                node = record["e"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                logger.debug(f"Created/merged entity: {entity.name}")
                logger.debug(f"[DEBUG] Entity operation completed successfully")
                return Entity(
                    id=UUID(node["id"]),
                    name=node["name"],
                    entity_type=node["entity_type"],
                    description=node.get("description"),
                    metadata=metadata,
                )
        except Exception as e:
            logger.error(f"[ERROR] Failed to create entity {entity.name}: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Entity details: type={entity.entity_type}, id={entity.id}")
            logger.exception(f"[EXCEPTION] Entity creation error:")
            raise

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
        logger.debug(f"[DEBUG] search_similar_chunks called: embedding_dim={len(embedding)}, top_k={top_k}")
        try:
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
            logger.debug(f"[DEBUG] Executing Neo4j similarity search query")
            results = []
            async with self._driver.session(database=self.database) as session:
                result = await session.run(query, {"embedding": embedding, "top_k": top_k})
                record_count = 0
                async for record in result:
                    record_count += 1
                    try:
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
                        logger.debug(f"[DEBUG] Processed search result {record_count}: chunk_id={chunk.id}, score={record['score']}")
                    except Exception as record_e:
                        logger.error(f"[ERROR] Failed to process search result {record_count}: {type(record_e).__name__}: {str(record_e)}")
                        logger.exception(f"[EXCEPTION] Search result processing error:")
                        # Continue with other results
                logger.debug(f"[DEBUG] Search completed with {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"[ERROR] search_similar_chunks failed: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Query params: embedding_dim={len(embedding)}, top_k={top_k}")
            logger.exception(f"[EXCEPTION] Similar chunks search error:")
            raise

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

    # Chunk Relationship Operations
    async def create_chunk_relationship(
        self,
        source_chunk_id: UUID,
        target_chunk_id: UUID,
        relation_type: str,
        weight: float = 1.0,
        description: Optional[str] = None,
    ) -> None:
        """Create relationship between chunks."""
        query = f"""
        MATCH (c1:Chunk {{id: $source_id}})
        MATCH (c2:Chunk {{id: $target_id}})
        MERGE (c1)-[r:{relation_type}]->(c2)
        SET r.weight = $weight, r.description = $description
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(
                query,
                {
                    "source_id": str(source_chunk_id),
                    "target_id": str(target_chunk_id),
                    "weight": weight,
                    "description": description,
                },
            )

    async def link_sequential_chunks(self, document_id: UUID) -> None:
        """Create FOLLOWS relationships between sequential chunks."""
        query = """
        MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
        WITH c ORDER BY c.chunk_index
        WITH collect(c) as chunks
        UNWIND range(0, size(chunks)-2) as i
        WITH chunks[i] as c1, chunks[i+1] as c2
        MERGE (c1)-[:FOLLOWS]->(c2)
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(query, {"doc_id": str(document_id)})
            logger.debug(f"Linked sequential chunks for document {document_id}")

    # Entity Mention Operations
    async def create_entity_mention(
        self,
        entity_id: UUID,
        chunk_id: UUID,
        mention_text: str,
        role: str = "CONTEXT",
        salience: float = 0.5,
        sentiment: Optional[float] = None,
        position: int = 0,
    ) -> None:
        """Create a rich entity mention with attributes."""
        query = """
        MATCH (c:Chunk {id: $chunk_id})
        MATCH (e:Entity {id: $entity_id})
        MERGE (c)-[m:MENTIONS]->(e)
        SET m.mention_text = $mention_text,
            m.role = $role,
            m.salience = $salience,
            m.sentiment = $sentiment,
            m.position = $position,
            m.confidence = 1.0
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(
                query,
                {
                    "chunk_id": str(chunk_id),
                    "entity_id": str(entity_id),
                    "mention_text": mention_text,
                    "role": role,
                    "salience": salience,
                    "sentiment": sentiment,
                    "position": position,
                },
            )

    # Advanced Search Operations
    async def search_with_vector_index(
        self, embedding: list[float], top_k: int = 10
    ) -> list[tuple[Chunk, float]]:
        """Search using HNSW vector index (Neo4j 5.11+)."""
        query = """
        CALL db.index.vector.queryNodes('chunk_embedding_index', $top_k, $embedding)
        YIELD node, score
        MATCH (d:Document)-[:HAS_CHUNK]->(node)
        RETURN node as c, d.id as document_id, score
        """
        
        results = []
        async with self._driver.session(database=self.database) as session:
            try:
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
                        summary=node.get("summary"),
                        topic=node.get("topic"),
                        semantic_density=node.get("semantic_density", 1.0),
                    )
                    results.append((chunk, record["score"]))
            except Exception as e:
                logger.warning(f"Vector index search failed, falling back to cosine: {e}")
                return await self.search_similar_chunks(embedding, top_k)
        
        return results

    async def fulltext_search_chunks(self, query: str, top_k: int = 10) -> list[Chunk]:
        """Full-text search on chunk content."""
        search_query = """
        CALL db.index.fulltext.queryNodes('chunk_content_fulltext', $query)
        YIELD node, score
        MATCH (d:Document)-[:HAS_CHUNK]->(node)
        RETURN node as c, d.id as document_id, score
        ORDER BY score DESC
        LIMIT $top_k
        """
        
        results = []
        async with self._driver.session(database=self.database) as session:
            try:
                result = await session.run(search_query, {"query": query, "top_k": top_k})
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
                    results.append(chunk)
            except Exception as e:
                logger.warning(f"Fulltext search failed: {e}")
        
        return results

    async def get_chunks_by_entities(
        self, entity_names: list[str], top_k: int = 10
    ) -> list[Chunk]:
        """Get chunks that mention specific entities."""
        query = """
        MATCH (e:Entity)
        WHERE e.name IN $entity_names OR e.canonical_name IN $entity_names
        MATCH (c:Chunk)-[:MENTIONS|CONTAINS_ENTITY]->(e)
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        WITH DISTINCT c, d, count(e) as entity_count
        RETURN c, d.id as document_id, entity_count
        ORDER BY entity_count DESC
        LIMIT $top_k
        """
        
        results = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"entity_names": entity_names, "top_k": top_k})
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
                results.append(chunk)
        
        return results

    async def get_related_chunks_via_entities(
        self, chunk_id: UUID, max_hops: int = 2, limit: int = 10
    ) -> list[tuple[Chunk, list[str]]]:
        """Get chunks related through entity relationships."""
        query = """
        MATCH (c1:Chunk {id: $chunk_id})-[:MENTIONS|CONTAINS_ENTITY]->(e1:Entity)
        MATCH (e1)-[:RELATED*1..%d]-(e2:Entity)
        MATCH (c2:Chunk)-[:MENTIONS|CONTAINS_ENTITY]->(e2)
        WHERE c1.id <> c2.id
        MATCH (d:Document)-[:HAS_CHUNK]->(c2)
        WITH c2, d, collect(DISTINCT e2.name) as entities
        RETURN c2, d.id as document_id, entities
        LIMIT $limit
        """ % max_hops
        
        results = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"chunk_id": str(chunk_id), "limit": limit})
            async for record in result:
                node = record["c2"]
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
                results.append((chunk, record["entities"]))
        return results
    
    async def get_related_chunks_via_relationships(
        self,
        chunk_id: UUID,
        relation_types: Optional[list[str]] = None,
        min_weight: float = 0.3,
        limit: int = 10,
    ) -> list[tuple[Chunk, str, float, Optional[str]]]:
        """Get chunks related via semantic chunk relationships.
        
        Returns list of (chunk, relation_type, weight, description) tuples.
        """
        # Build relation type filter
        rel_filter = ""
        if relation_types:
            rel_types_str = "|".join(relation_types)
            rel_filter = f":{rel_types_str}"
        
        query = f"""
        MATCH (c:Chunk {{id: $chunk_id}})-[r{rel_filter}]->(related:Chunk)
        WHERE r.weight >= $min_weight
        MATCH (d:Document)-[:HAS_CHUNK]->(related)
        RETURN related, d.id as document_id, type(r) as rel_type, r.weight as weight, r.description as description
        ORDER BY r.weight DESC
        LIMIT $limit
        """
        
        results = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(
                query,
                {
                    "chunk_id": str(chunk_id),
                    "min_weight": min_weight,
                    "limit": limit,
                },
            )
            async for record in result:
                node = record["related"]
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
                rel_type = record["rel_type"]
                weight = record["weight"]
                description = record.get("description")
                results.append((chunk, rel_type, weight, description))
            return results
        
        return results

    async def get_chunks_in_community(
        self, community_id: UUID, limit: int = 20
    ) -> list[Chunk]:
        """Get all chunks associated with a community."""
        query = """
        MATCH (com:Community {id: $community_id})<-[:BELONGS_TO]-(e:Entity)
        MATCH (c:Chunk)-[:MENTIONS|CONTAINS_ENTITY]->(e)
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        WITH DISTINCT c, d
        RETURN c, d.id as document_id
        LIMIT $limit
        """
        
        results = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"community_id": str(community_id), "limit": limit})
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
                results.append(chunk)
        
        return results

    async def find_shortest_path_between_entities(
        self, entity1_name: str, entity2_name: str, max_hops: int = 5
    ) -> list[dict]:
        """Find shortest path between two entities."""
        query = """
        MATCH (e1:Entity {name: $name1}), (e2:Entity {name: $name2})
        MATCH path = shortestPath((e1)-[:RELATED*1..%d]-(e2))
        RETURN [node in nodes(path) | {name: node.name, type: node.entity_type}] as path_nodes,
               [rel in relationships(path) | type(rel)] as relationship_types
        LIMIT 1
        """ % max_hops
        
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"name1": entity1_name, "name2": entity2_name})
            record = await result.single()
            if record:
                return {
                    'nodes': record['path_nodes'],
                    'relationships': record['relationship_types'],
                }
        
        return {}

    async def get_entity_summary_from_chunks(self, entity_id: UUID) -> str:
        """Generate entity summary from all chunk mentions."""
        query = """
        MATCH (e:Entity {id: $entity_id})<-[:MENTIONS|CONTAINS_ENTITY]-(c:Chunk)
        RETURN c.content as content
        LIMIT 10
        """
        
        contents = []
        async with self._driver.session(database=self.database) as session:
            result = await session.run(query, {"entity_id": str(entity_id)})
            async for record in result:
                contents.append(record["content"])
        
        if contents:
            # Simple summary: combine first sentences
            summary_parts = []
            for content in contents:
                sentences = content.split('.')
                if sentences:
                    summary_parts.append(sentences[0].strip())
            return '. '.join(summary_parts[:3]) + '.'
        
        return ""

    async def update_entity_with_disambiguation(
        self,
        entity_id: UUID,
        canonical_name: str,
        aliases: list[str],
        confidence: float,
    ) -> None:
        """Update entity with disambiguation info."""
        query = """
        MATCH (e:Entity {id: $entity_id})
        SET e.canonical_name = $canonical_name,
            e.aliases = $aliases,
            e.confidence = $confidence
        """
        async with self._driver.session(database=self.database) as session:
            await session.run(
                query,
                {
                    "entity_id": str(entity_id),
                    "canonical_name": canonical_name,
                    "aliases": aliases,
                    "confidence": confidence,
                },
            )

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
