# Smart RAG - Hierarchical Graph-of-Graphs RAG System

A production-ready, hierarchical Graph-of-Graphs Retrieval-Augmented Generation (RAG) system built with FastAPI, Neo4j, and modern LLM technologies.

## Features

- **Hierarchical Graph Construction**: Multi-level knowledge graph with community detection
- **Advanced Document Processing**: Intelligent chunking, entity extraction, and embedding generation
- **Graph-of-Graphs Architecture**: Hierarchical clustering with multiple abstraction levels
- **Semantic Retrieval**: Vector similarity search combined with graph traversal
- **Context-Aware Answering**: LLM-powered answers with source attribution
- **Async/Await**: Full asynchronous API for high performance
- **Production Ready**: Docker support, comprehensive logging, error handling

## Architecture

```
Documents → Chunks → Entities → Local Graphs → Communities → Hierarchical Graph-of-Graphs
                                                                         ↓
                                                                   Query Engine
                                                                         ↓
                                                              Retrieval + Reranking
                                                                         ↓
                                                                   LLM Answer
```

## Quick Start

### Prerequisites

- Python 3.11+
- Neo4j 5.0+
- OpenAI API Key
- UV package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd smart_rag
```

2. Install UV (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create virtual environment and install dependencies:
```bash
uv venv
uv pip install -e .
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Start Neo4j (using Docker):
```bash
docker-compose up -d neo4j
```

6. Run the application:
```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## Docker Deployment

```bash
docker-compose up -d
```

This starts:
- Neo4j graph database (port 7474, 7687)
- Smart RAG API (port 8000)

## API Endpoints

### Document Management

- `POST /api/v1/documents/upload` - Upload and process documents
- `GET /api/v1/documents/{doc_id}` - Get document details
- `DELETE /api/v1/documents/{doc_id}` - Delete document and associated graph

### Query

- `POST /api/v1/query` - Ask questions and get answers with sources
- `POST /api/v1/query/search` - Semantic search without LLM generation

### Graph Management

- `GET /api/v1/graph/stats` - Get graph statistics
- `POST /api/v1/graph/rebuild` - Rebuild hierarchical graph
- `GET /api/v1/graph/communities` - List detected communities

### Health

- `GET /health` - Health check endpoint

## API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | LLM model name | gpt-4-turbo-preview |
| `NEO4J_URI` | Neo4j connection URI | bolt://localhost:7687 |
| `CHUNK_SIZE` | Document chunk size | 1000 |
| `TOP_K_RETRIEVAL` | Number of chunks to retrieve | 10 |
| `MAX_HIERARCHY_LEVELS` | Maximum graph hierarchy depth | 3 |

See `.env.example` for all configuration options.

## Development

### Run tests

```bash
uv pip install -e ".[dev]"
uv run pytest
```

### Code formatting

```bash
uv run black .
uv run ruff check .
```

### Type checking

```bash
uv run mypy app/
```

## Project Structure

```
smart_rag/
├── app/
│   ├── api/              # FastAPI routes and endpoints
│   ├── core/             # Configuration, logging, dependencies
│   ├── domain/           # Domain models and business logic
│   ├── services/         # Business logic services
│   ├── repositories/     # Data access layer
│   └── main.py           # Application entry point
├── tests/                # Test suite
├── data/                 # Data storage
├── docker/               # Docker configurations
├── pyproject.toml        # Project metadata and dependencies
└── README.md
```

## Core Components

### Document Processor
Handles document ingestion, chunking, and embedding generation.

### Entity Extractor
Extracts named entities and relationships using LLM.

### Graph Builder
Constructs local graphs from entities and builds hierarchical communities.

### Query Engine
Retrieves relevant context and generates answers using LLM.

### Neo4j Repository
Manages all graph database operations.

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
