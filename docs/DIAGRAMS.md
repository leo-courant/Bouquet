# System Diagrams

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Client Layer                              │
│  (Web Browser, Mobile App, CLI, API Client, Python SDK, etc.)      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP/REST
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                         FastAPI Server                               │
│  ┌────────────────┬──────────────────┬─────────────────────────┐   │
│  │   Documents    │      Query       │        Graph           │   │
│  │   Endpoints    │    Endpoints     │      Endpoints         │   │
│  │                │                  │                        │   │
│  │ • Upload       │ • Ask Question   │ • Get Stats           │   │
│  │ • Create       │ • Search         │ • Rebuild             │   │
│  │ • Read         │ • Get Related    │ • List Communities    │   │
│  │ • Delete       │                  │ • Clear Data          │   │
│  └────────┬───────┴──────┬───────────┴─────────┬─────────────┘   │
└───────────┼──────────────┼─────────────────────┼─────────────────┘
            │              │                     │
┌───────────▼──────────────▼─────────────────────▼─────────────────┐
│                      Service Layer                                 │
│  ┌──────────────────┬──────────────────┬────────────────────┐    │
│  │   Document       │    Query         │      Graph         │    │
│  │   Processor      │    Engine        │     Builder        │    │
│  │                  │                  │                    │    │
│  │ • Chunk Text     │ • Embed Query    │ • Detect           │    │
│  │ • Extract        │ • Search Graph   │   Communities      │    │
│  │   Entities       │ • Rerank         │ • Build Hierarchy  │    │
│  │ • Generate       │ • Generate       │ • Create           │    │
│  │   Embeddings     │   Answer         │   Summaries        │    │
│  └──────┬───────────┴──────┬───────────┴─────┬──────────────┘    │
│         │                  │                 │                    │
│  ┌──────▼──────────┐  ┌───▼────────────┐   │                    │
│  │   Embedding     │  │    Entity      │   │                    │
│  │    Service      │  │   Extractor    │   │                    │
│  │                 │  │                │   │                    │
│  │ • OpenAI API    │  │ • GPT-4 API    │   │                    │
│  │ • Batch Embed   │  │ • Extract NER  │   │                    │
│  │ • Similarity    │  │ • Relationships│   │                    │
│  └─────────────────┘  └────────────────┘   │                    │
└───────────────────────────────────────────┼────────────────────┘
                                            │
┌───────────────────────────────────────────▼────────────────────┐
│                    Repository Layer                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Neo4j Repository                            │  │
│  │                                                          │  │
│  │ • Connect/Disconnect      • Search Similarity          │  │
│  │ • Create/Read/Update      • Get Entities               │  │
│  │ • Delete Operations       • Graph Traversal            │  │
│  │ • Community Management    • Statistics                 │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    Neo4j Graph Database                          │
│  ┌──────────────┬─────────────┬────────────┬─────────────────┐ │
│  │  Documents   │   Chunks    │  Entities  │  Communities    │ │
│  │              │             │            │                 │ │
│  │ • Metadata   │ • Content   │ • Names    │ • Level         │ │
│  │ • Content    │ • Embedding │ • Types    │ • Members       │ │
│  │              │             │            │ • Summary       │ │
│  └──────┬───────┴──────┬──────┴─────┬──────┴──────┬──────────┘ │
│         │              │            │             │            │
│    HAS_CHUNK    CONTAINS_ENTITY  RELATED    BELONGS_TO        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

External Services:
┌──────────────────────┐
│     OpenAI API       │
│                      │
│ • GPT-4              │
│ • text-embedding-3   │
│ • Chat Completions   │
└──────────────────────┘
```

## Data Flow - Document Ingestion

```
┌─────────────┐
│   Upload    │
│  Document   │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────┐
│     Document Processor                   │
│  ┌────────────────────────────────────┐ │
│  │  1. Parse & Validate               │ │
│  └────────────┬───────────────────────┘ │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  2. Create Chunks                  │ │
│  │     • Intelligent splitting        │ │
│  │     • Sentence boundaries          │ │
│  │     • Configurable overlap         │ │
│  └────────────┬───────────────────────┘ │
└───────────────┼──────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌───────────────┐  ┌────────────────┐
│   Embedding   │  │     Entity     │
│    Service    │  │   Extractor    │
│               │  │                │
│ Generate      │  │ Extract:       │
│ Vectors       │  │ • Entities     │
│ (OpenAI)      │  │ • Relations    │
│               │  │ (GPT-4)        │
└───────┬───────┘  └────────┬───────┘
        │                   │
        └─────────┬─────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  Neo4j Repository   │
        │                     │
        │  Store:             │
        │  • Document node    │
        │  • Chunk nodes      │
        │  • Entity nodes     │
        │  • Relationships    │
        └─────────────────────┘
```

## Data Flow - Graph Building

```
┌──────────────────────┐
│   Trigger Rebuild    │
└──────────┬───────────┘
           │
           ▼
┌────────────────────────────────────────┐
│        Graph Builder                   │
│  ┌──────────────────────────────────┐ │
│  │  1. Load Entity Graph from DB    │ │
│  │     MATCH (e1)-[r]-(e2)          │ │
│  └──────────┬───────────────────────┘ │
│             ▼                          │
│  ┌──────────────────────────────────┐ │
│  │  2. Detect Communities (Louvain) │ │
│  │     • Level 0: Base entities     │ │
│  └──────────┬───────────────────────┘ │
│             ▼                          │
│  ┌──────────────────────────────────┐ │
│  │  3. Create Community Nodes       │ │
│  │     • Generate summaries         │ │
│  │     • Create embeddings          │ │
│  └──────────┬───────────────────────┘ │
│             ▼                          │
│  ┌──────────────────────────────────┐ │
│  │  4. Build Next Level             │ │
│  │     • Community graph            │ │
│  │     • Detect meta-communities    │ │
│  └──────────┬───────────────────────┘ │
│             ▼                          │
│  ┌──────────────────────────────────┐ │
│  │  5. Repeat Until Max Levels      │ │
│  │     or Single Community          │ │
│  └──────────────────────────────────┘ │
└────────────────────────────────────────┘

Result:
┌─────────────────────────────────────┐
│     Hierarchical Graph-of-Graphs    │
│                                     │
│  Level 2: ┌─────────────────┐      │
│           │  Meta-Community │      │
│           └────────┬────────┘      │
│                    │                │
│  Level 1: ┌───────┴────────┐       │
│           │   Communities  │       │
│           └───────┬────────┘       │
│                   │                 │
│  Level 0: ┌──────┴──────┐          │
│           │   Entities  │          │
│           └─────────────┘          │
└─────────────────────────────────────┘
```

## Data Flow - Query Processing

```
┌─────────────────┐
│   User Query    │
│ "What is AI?"   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│         Query Engine                     │
│  ┌────────────────────────────────────┐ │
│  │  1. Generate Query Embedding       │ │
│  │     (OpenAI Embeddings API)        │ │
│  └──────────┬─────────────────────────┘ │
│             ▼                            │
│  ┌────────────────────────────────────┐ │
│  │  2. Vector Similarity Search       │ │
│  │     • Search chunk embeddings      │ │
│  │     • Get top-K matches            │ │
│  │     • Cypher + cosine similarity   │ │
│  └──────────┬─────────────────────────┘ │
│             ▼                            │
│  ┌────────────────────────────────────┐ │
│  │  3. Retrieve Context               │ │
│  │     • Get chunks                   │ │
│  │     • Get related entities         │ │
│  │     • Graph traversal              │ │
│  └──────────┬─────────────────────────┘ │
│             ▼                            │
│  ┌────────────────────────────────────┐ │
│  │  4. Rerank Results                 │ │
│  │     • Score by relevance           │ │
│  │     • Select top results           │ │
│  └──────────┬─────────────────────────┘ │
│             ▼                            │
│  ┌────────────────────────────────────┐ │
│  │  5. Build Context String           │ │
│  │     • Concatenate chunks           │ │
│  │     • Respect max length           │ │
│  │     • Add source markers           │ │
│  └──────────┬─────────────────────────┘ │
│             ▼                            │
│  ┌────────────────────────────────────┐ │
│  │  6. Generate Answer (GPT-4)        │ │
│  │     • Context + Question           │ │
│  │     • System prompt                │ │
│  │     • Extract answer               │ │
│  └──────────┬─────────────────────────┘ │
└─────────────┼──────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────┐
│         Response                         │
│  ┌────────────────────────────────────┐ │
│  │  Answer: "AI is..."                │ │
│  │                                    │ │
│  │  Sources:                          │ │
│  │  [1] Document: "Intro to AI"       │ │
│  │      Score: 0.92                   │ │
│  │      Content: "..."                │ │
│  │  [2] Document: "ML Basics"         │ │
│  │      Score: 0.87                   │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

## Database Schema

```
┌──────────────────────────────────────────────────────────────┐
│                    Neo4j Graph Schema                         │
└──────────────────────────────────────────────────────────────┘

Nodes:

┌───────────────┐
│   Document    │
│───────────────│
│ id: UUID      │
│ title: str    │
│ content: str  │
│ source: str   │
│ metadata: {}  │
│ created_at    │
│ updated_at    │
└───────┬───────┘
        │ HAS_CHUNK
        │
        ▼
┌───────────────┐
│     Chunk     │
│───────────────│
│ id: UUID      │
│ content: str  │
│ embedding: [] │
│ chunk_index   │
│ start_char    │
│ end_char      │
│ metadata: {}  │
└───────┬───────┘
        │ CONTAINS_ENTITY
        │
        ▼
┌───────────────┐         ┌──────────────┐
│    Entity     │◄────────│  Community   │
│───────────────│ BELONGS │──────────────│
│ id: UUID      │    TO   │ id: UUID     │
│ name: str     │         │ level: int   │
│ entity_type   │         │ summary: str │
│ description   │         │ embedding:[] │
│ metadata: {}  │         │ properties   │
└───────┬───────┘         └──────┬───────┘
        │                        │
        │ RELATED                │ PART_OF
        │ (weight)               │
        ▼                        ▼
┌───────────────┐         ┌──────────────┐
│    Entity     │         │  Community   │
│               │         │  (Higher     │
│               │         │   Level)     │
└───────────────┘         └──────────────┘

Indexes:
• Document.id
• Chunk.id
• Entity.id
• Entity.name
• Community.id
• Community.level
```

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Production Deployment                      │
└──────────────────────────────────────────────────────────────┘

Internet
    │
    ▼
┌─────────────────────┐
│   Load Balancer     │
│   (NGINX/AWS ALB)   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌──────────┐  ┌──────────┐
│  API     │  │  API     │
│ Instance │  │ Instance │
│   #1     │  │   #2     │
│ (Docker) │  │ (Docker) │
└─────┬────┘  └─────┬────┘
      │             │
      └──────┬──────┘
             │
    ┌────────┴─────────┐
    │                  │
    ▼                  ▼
┌──────────────┐  ┌───────────────┐
│   Neo4j      │  │    Redis      │
│  Cluster     │  │    Cache      │
│  (Primary +  │  │  (Optional)   │
│   Replicas)  │  │               │
└──────────────┘  └───────────────┘

External:
┌──────────────┐
│  OpenAI API  │
└──────────────┘

Monitoring:
┌────────────┬─────────────┬──────────────┐
│ Prometheus │  Grafana    │     ELK      │
│  Metrics   │  Dashboard  │   Logging    │
└────────────┴─────────────┴──────────────┘
```
