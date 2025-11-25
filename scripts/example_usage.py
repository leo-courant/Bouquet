#!/usr/bin/env python3
"""Example script for using the Smart RAG system."""

import asyncio
from uuid import UUID

from app.core import (
    get_document_processor,
    get_embedding_service,
    get_entity_extractor,
    get_graph_builder,
    get_neo4j_repository,
    get_query_engine,
)


async def main():
    """Run example usage."""
    print("Smart RAG Example Usage\n" + "=" * 50)

    # Initialize components
    repository = None
    try:
        # Get repository
        async for repo in get_neo4j_repository():
            repository = repo
            break

        # Get services
        embedding_service = await get_embedding_service()
        entity_extractor = await get_entity_extractor()
        document_processor = await get_document_processor(embedding_service, entity_extractor)
        graph_builder = await get_graph_builder(repository)
        query_engine = await get_query_engine(repository, embedding_service)

        # Example 1: Process a document
        print("\n1. Processing a sample document...")
        sample_text = """
        Artificial Intelligence (AI) is transforming healthcare. Machine learning algorithms
        can now detect diseases from medical images with high accuracy. Deep learning models
        are being used to predict patient outcomes and personalize treatment plans.
        
        Natural Language Processing (NLP) helps extract insights from clinical notes.
        Researchers at Stanford University have developed AI systems that can diagnose
        skin cancer as accurately as dermatologists.
        """

        document = await document_processor.process_text(
            text=sample_text,
            title="AI in Healthcare",
            repository=repository,
            source="example.txt",
        )
        print(f"✓ Processed document: {document.title} (ID: {document.id})")

        # Example 2: Build hierarchical graph
        print("\n2. Building hierarchical graph structure...")
        result = await graph_builder.rebuild_graph(embedding_service)
        print(f"✓ Built {result['total_levels']} levels with {result['total_communities']} communities")

        # Example 3: Query the system
        print("\n3. Querying the knowledge graph...")
        query = "How is AI being used in healthcare?"
        response = await query_engine.query(query)

        print(f"\nQuery: {query}")
        print(f"Answer: {response.answer}")
        print(f"\nSources ({len(response.sources)}):")
        for i, source in enumerate(response.sources[:3], 1):
            print(f"  [{i}] Score: {source.score:.3f}")
            print(f"      {source.content[:100]}...")

        # Example 4: Get graph statistics
        print("\n4. Graph statistics...")
        stats = await repository.get_graph_stats()
        print(f"✓ Total nodes: {stats.total_nodes}")
        print(f"✓ Total edges: {stats.total_edges}")
        print(f"✓ Nodes by type: {stats.nodes_by_type}")

    finally:
        if repository:
            await repository.close()

    print("\n" + "=" * 50)
    print("Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
