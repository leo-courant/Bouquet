"""API endpoints for graph management and statistics."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.core import get_embedding_service, get_graph_builder, get_neo4j_repository
from app.domain import GraphStats
from app.repositories import Neo4jRepository
from app.services import EmbeddingService, GraphBuilder

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> GraphStats:
    """Get statistics about the knowledge graph."""
    try:
        stats = await repository.get_graph_stats()
        return stats

    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting graph stats: {str(e)}",
        )


@router.post("/rebuild", response_model=None)
async def rebuild_graph(
    graph_builder: GraphBuilder = Depends(get_graph_builder),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """Rebuild the hierarchical graph-of-graphs structure."""
    try:
        result = await graph_builder.rebuild_graph(embedding_service)
        return {
            "status": "success",
            "message": "Graph rebuilt successfully",
            **result,
        }

    except Exception as e:
        logger.error(f"Error rebuilding graph: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error rebuilding graph: {str(e)}",
        )


@router.get("/communities", response_model=list[dict])
async def list_communities(
    level: int = None,
    limit: int = 100,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> list[dict]:
    """List communities in the graph."""
    if level is not None:
        query = """
        MATCH (c:Community {level: $level})
        RETURN c.id as id, c.level as level, c.summary as summary, 
               size((n)-[:BELONGS_TO]->(c)) as member_count
        ORDER BY member_count DESC
        LIMIT $limit
        """
        params = {"level": level, "limit": limit}
    else:
        query = """
        MATCH (c:Community)
        RETURN c.id as id, c.level as level, c.summary as summary,
               size((n)-[:BELONGS_TO]->(c)) as member_count
        ORDER BY c.level, member_count DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    communities = []
    async with repository._driver.session(database=repository.database) as session:
        result = await session.run(query, params)
        async for record in result:
            communities.append({
                "id": record["id"],
                "level": record["level"],
                "summary": record["summary"],
                "member_count": record["member_count"],
            })

    return communities


@router.get("/communities/{community_id}/members", response_model=list[dict])
async def get_community_members(
    community_id: str,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> list[dict]:
    """Get members of a specific community."""
    query = """
    MATCH (n)-[:BELONGS_TO]->(c:Community {id: $community_id})
    RETURN n.id as id, n.name as name, labels(n) as labels
    LIMIT 100
    """

    members = []
    async with repository._driver.session(database=repository.database) as session:
        result = await session.run(query, {"community_id": community_id})
        async for record in result:
            members.append({
                "id": record["id"],
                "name": record.get("name", "N/A"),
                "type": record["labels"][0] if record["labels"] else "Unknown",
            })

    return members


@router.get("/visualize", response_model=dict)
async def get_graph_visualization(
    limit: int = 200,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> dict:
    """Get graph data for visualization (nodes and edges)."""
    try:
        # Query for nodes (entities, chunks, documents, communities)
        nodes_query = """
        MATCH (n)
        WHERE n:Entity OR n:Chunk OR n:Document OR n:Community
        WITH n, labels(n) as nodeLabels
        RETURN n.id as id, 
               coalesce(n.name, n.title, n.id, 'Node-' + toString(id(n))) as label,
               nodeLabels[0] as type,
               n.type as entityType,
               n.level as level,
               n.summary as summary,
               n.content as content
        LIMIT $limit
        """
        
        # Query for relationships
        edges_query = """
        MATCH (n)-[r]->(m)
        WHERE (n:Entity OR n:Chunk OR n:Document OR n:Community) 
          AND (m:Entity OR m:Chunk OR m:Document OR m:Community)
        RETURN n.id as source, 
               m.id as target, 
               type(r) as type,
               r.weight as weight,
               r.description as description
        LIMIT $limit
        """
        
        nodes = []
        edges = []
        
        async with repository._driver.session(database=repository.database) as session:
            # Fetch nodes
            result = await session.run(nodes_query, {"limit": limit})
            async for record in result:
                node = {
                    "id": str(record["id"]),
                    "label": record["label"],
                    "type": record["type"],
                }
                # Add optional fields
                if record.get("entityType"):
                    node["entityType"] = record["entityType"]
                if record.get("level") is not None:
                    node["level"] = record["level"]
                if record.get("summary"):
                    node["summary"] = record["summary"][:200]  # Truncate
                if record.get("content"):
                    node["content"] = record["content"][:200]  # Truncate
                nodes.append(node)
            
            # Fetch edges
            result = await session.run(edges_query, {"limit": limit})
            async for record in result:
                edge = {
                    "source": str(record["source"]),
                    "target": str(record["target"]),
                    "type": record["type"],
                }
                if record.get("weight") is not None:
                    edge["weight"] = record["weight"]
                if record.get("description"):
                    edge["description"] = record["description"]
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "count": {
                "nodes": len(nodes),
                "edges": len(edges),
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting graph visualization: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting graph visualization: {str(e)}",
        )


@router.delete("/clear", response_model=None)
async def clear_graph(
    confirm: bool = False,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
):
    """Clear all data from the graph (requires confirmation)."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to clear all graph data",
        )

    try:
        await repository.clear_all()
        return {
            "status": "success",
            "message": "All graph data cleared successfully",
        }

    except Exception as e:
        logger.error(f"Error clearing graph: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing graph: {str(e)}",
        )
