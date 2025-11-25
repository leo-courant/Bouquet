# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Client                               │
│                    (REST API Calls)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      FastAPI                                 │
│  ┌──────────────┬──────────────┬──────────────────────┐    │
│  │  Documents   │    Query     │       Graph          │    │
│  │  Endpoints   │  Endpoints   │     Endpoints        │    │
│  └──────┬───────┴──────┬───────┴──────────┬──────────┘    │
└─────────┼──────────────┼──────────────────┼───────────────┘
          │              │                  │
┌─────────▼──────────────▼──────────────────▼───────────────┐
│                    Service Layer                            │
│  ┌────────────────┬──────────────┬──────────────────┐     │
│  │   Document     │    Query     │      Graph       │     │
│  │   Processor    │    Engine    │     Builder      │     │
│  └────────┬───────┴──────┬───────┴──────────┬───────┘     │
│           │              │                  │             │
│  ┌────────▼──────┬───────▼─────┐            │             │
│  │  Embedding    │   Entity    │            │             │
│  │   Service     │  Extractor  │            │             │
│  └───────────────┴─────────────┘            │             │
└─────────────────────────────────────────────┼─────────────┘
                                              │
┌─────────────────────────────────────────────▼─────────────┐
│                 Repository Layer                            │
│              (Neo4j Repository)                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Neo4j Database                          │
│                  (Knowledge Graph)                           │
└──────────────────────────────────────────────────────────────┘

External Services:
┌──────────────────┐
│   OpenAI API     │
│  - GPT-4         │
│  - Embeddings    │
└──────────────────┘
```

## Data Flow

### 1. Document Ingestion

```
Document Upload
    ↓
Text Chunking
    ↓
Parallel Processing:
    ├─→ Embedding Generation (OpenAI)
    └─→ Entity Extraction (GPT-4)
    ↓
Graph Storage (Neo4j)
    ├─→ Document Node
    ├─→ Chunk Nodes (with embeddings)
    ├─→ Entity Nodes
    └─→ Relationship Edges
```

### 2. Hierarchical Graph Construction

```
Entity Graph
    ↓
Community Detection (Louvain)
    ↓
Level 0 Communities
    ↓
Inter-Community Graph
    ↓
Community Detection
    ↓
Level 1 Communities
    ↓
Repeat until convergence or max levels
    ↓
Graph-of-Graphs Structure
```

### 3. Query Processing

```
User Query
    ↓
Query Embedding Generation
    ↓
Vector Similarity Search
    ↓
Retrieve Top-K Chunks
    ↓
Re-ranking
    ↓
Context Building
    ↓
LLM Answer Generation
    ↓
Response with Sources
```

## Component Details

### Core Components

#### 1. Document Processor
- **Purpose**: Process raw documents into structured knowledge
- **Key Functions**:
  - Text chunking with overlap
  - Embedding generation
  - Entity and relationship extraction
- **Dependencies**: EmbeddingService, EntityExtractor, Neo4jRepository

#### 2. Entity Extractor
- **Purpose**: Extract structured knowledge from text
- **Key Functions**:
  - Named entity recognition
  - Relationship extraction
  - Summary generation
- **Technology**: GPT-4 with structured output

#### 3. Embedding Service
- **Purpose**: Generate vector embeddings
- **Key Functions**:
  - Single and batch embedding generation
  - Similarity computation
- **Technology**: OpenAI text-embedding-3-large

#### 4. Graph Builder
- **Purpose**: Construct hierarchical graph structure
- **Key Functions**:
  - Community detection (Louvain algorithm)
  - Hierarchical clustering
  - Graph-of-graphs construction
- **Technology**: NetworkX, python-louvain

#### 5. Query Engine
- **Purpose**: Answer questions using RAG
- **Key Functions**:
  - Semantic search
  - Result re-ranking
  - Context-aware answer generation
  - Graph traversal for related entities
- **Technology**: Vector similarity + GPT-4

#### 6. Neo4j Repository
- **Purpose**: Manage graph database operations
- **Key Functions**:
  - CRUD operations for all node types
  - Vector similarity search
  - Graph traversal queries
  - Statistics and analytics
- **Technology**: Neo4j async driver

### Database Schema

#### Node Types

1. **Document**
   - Properties: id, title, content, source, metadata, created_at, updated_at
   - Relationships: -[:HAS_CHUNK]→ Chunk

2. **Chunk**
   - Properties: id, content, embedding, chunk_index, start_char, end_char, metadata, created_at
   - Relationships: 
     - ←[:HAS_CHUNK]- Document
     - -[:CONTAINS_ENTITY]→ Entity

3. **Entity**
   - Properties: id, name, entity_type, description, metadata
   - Relationships:
     - ←[:CONTAINS_ENTITY]- Chunk
     - -[:RELATED]→ Entity
     - -[:BELONGS_TO]→ Community

4. **Community**
   - Properties: id, level, summary, embedding, properties, created_at
   - Relationships:
     - ←[:BELONGS_TO]- Entity/Community
     - -[:PART_OF]→ Community (parent)

#### Edge Types

- **HAS_CHUNK**: Document → Chunk
- **CONTAINS_ENTITY**: Chunk → Entity
- **RELATED**: Entity → Entity (weighted)
- **BELONGS_TO**: Entity/Community → Community
- **PART_OF**: Community → Community (hierarchical)

## Scalability Considerations

### Horizontal Scaling
- FastAPI: Multiple worker processes
- Neo4j: Causal clustering for read replicas
- Caching: Redis for frequently accessed data

### Performance Optimization
- Batch processing for embeddings
- Async/await throughout
- Connection pooling
- Index optimization
- Query result caching

### Resource Management
- Configurable chunk sizes
- Rate limiting on API endpoints
- Background job processing for large documents
- Incremental graph updates

## Security

- API key authentication (extensible)
- Input validation with Pydantic
- SQL injection prevention (parameterized queries)
- CORS configuration
- Environment variable management
- Secrets management with .env files
