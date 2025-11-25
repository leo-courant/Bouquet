#!/usr/bin/env python3
"""Script to initialize the database with sample data."""

import asyncio

from app.core import (
    get_document_processor,
    get_embedding_service,
    get_entity_extractor,
    get_graph_builder,
    get_neo4j_repository,
)


SAMPLE_DOCUMENTS = [
    {
        "title": "Introduction to Machine Learning",
        "content": """
        Machine Learning is a subset of Artificial Intelligence that focuses on building
        systems that learn from data. The main types of machine learning are supervised learning,
        unsupervised learning, and reinforcement learning.
        
        Supervised learning involves training models on labeled data. Common algorithms include
        linear regression, decision trees, and neural networks. These algorithms learn to map
        inputs to outputs based on example input-output pairs.
        
        Unsupervised learning finds patterns in unlabeled data. Clustering algorithms like
        K-means and hierarchical clustering group similar data points. Dimensionality reduction
        techniques like PCA help visualize high-dimensional data.
        """,
        "source": "ml_intro.txt",
    },
    {
        "title": "Deep Learning Fundamentals",
        "content": """
        Deep Learning is a branch of machine learning based on artificial neural networks.
        Deep neural networks contain multiple hidden layers that can learn hierarchical
        representations of data.
        
        Convolutional Neural Networks (CNNs) excel at computer vision tasks. They use
        convolutional layers to automatically learn spatial hierarchies of features from images.
        Applications include image classification, object detection, and image segmentation.
        
        Recurrent Neural Networks (RNNs) are designed for sequential data. Long Short-Term
        Memory (LSTM) networks and Transformers have revolutionized natural language processing.
        They power applications like machine translation, text generation, and chatbots.
        """,
        "source": "deep_learning.txt",
    },
    {
        "title": "Natural Language Processing",
        "content": """
        Natural Language Processing (NLP) enables computers to understand and generate human language.
        Modern NLP relies heavily on deep learning and transformer architectures.
        
        BERT (Bidirectional Encoder Representations from Transformers) revolutionized NLP by
        introducing bidirectional context understanding. It achieved state-of-the-art results
        on many NLP benchmarks.
        
        GPT (Generative Pre-trained Transformer) models excel at text generation. GPT-3 and
        GPT-4 demonstrate remarkable capabilities in various language tasks including
        question answering, summarization, and code generation.
        """,
        "source": "nlp.txt",
    },
]


async def main():
    """Initialize database with sample data."""
    print("Initializing database with sample data\n" + "=" * 50)

    repository = None
    try:
        # Get repository
        async for repo in get_neo4j_repository():
            repository = repo
            break

        print(f"\n✓ Connected to Neo4j at {repository.uri}")

        # Get services
        embedding_service = await get_embedding_service()
        entity_extractor = await get_entity_extractor()
        document_processor = await get_document_processor(embedding_service, entity_extractor)
        graph_builder = await get_graph_builder(repository)

        # Process sample documents
        print(f"\nProcessing {len(SAMPLE_DOCUMENTS)} sample documents...")
        for i, doc_data in enumerate(SAMPLE_DOCUMENTS, 1):
            print(f"\n[{i}/{len(SAMPLE_DOCUMENTS)}] {doc_data['title']}...")
            await document_processor.process_text(
                text=doc_data["content"],
                title=doc_data["title"],
                repository=repository,
                source=doc_data["source"],
            )
            print(f"  ✓ Processed")

        # Build hierarchical graph
        print("\nBuilding hierarchical graph structure...")
        result = await graph_builder.rebuild_graph(embedding_service)
        print(f"✓ Built {result['total_levels']} levels")
        print(f"✓ Created {result['total_communities']} communities")

        # Show statistics
        stats = await repository.get_graph_stats()
        print("\nGraph Statistics:")
        print(f"  Nodes: {stats.total_nodes}")
        print(f"  Edges: {stats.total_edges}")
        print(f"  By type: {stats.nodes_by_type}")

    finally:
        if repository:
            await repository.close()

    print("\n" + "=" * 50)
    print("Initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
