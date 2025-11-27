# Smart RAG - Hierarchical Graph-of-Graphs RAG System

A production-ready, hierarchical Graph-of-Graphs Retrieval-Augmented Generation (RAG) system built with FastAPI, Neo4j, and modern LLM technologies.

## Features

- **Web Interface**: Simple, intuitive chat interface with document upload and graph visualization
- **Hierarchical Graph Construction**: Multi-level knowledge graph with community detection
- **Advanced Document Processing**: Intelligent chunking, entity extraction, and embedding generation
- **Graph-of-Graphs Architecture**: Hierarchical clustering with multiple abstraction levels
- **Interactive Graph Visualization**: Explore your knowledge graph with D3.js-powered visualizations
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
- Docker and Docker Compose
- OpenAI API Key
- Make (optional, but recommended)

### Installation

**Two options: Local Development (recommended) or Full Docker**

#### Option 1: Local Development (Recommended)

Run Neo4j in Docker, but run your app locally for faster development:

```bash
# Setup environment
make setup

# Edit .env file with your OpenAI API key and Neo4j password
nano .env

# Start development mode (starts Neo4j + runs app locally with auto-reload)
make dev
```

This will:
- Start Neo4j in Docker
- Run the FastAPI app locally with hot-reload
- Any changes to your code will automatically restart the server
- Access the web interface at http://localhost:8000

To stop: Press `Ctrl+C`, then run `docker compose down` to stop Neo4j.

#### Option 2: Full Docker Deployment

Run everything in Docker containers:

```bash
# Setup and build
make setup
# Edit .env with your configuration
make build
make up
```

5. Check health:
```bash
make health
```

The API will be available at `http://localhost:8000`

## Using the Web Interface

After starting the services, open your browser and navigate to:

**http://localhost:8000**

The web interface provides:

### 📄 Document Upload
- **Drag & Drop**: Drop files directly into the upload area
- **Click to Browse**: Select multiple files from your computer
- **Supported Formats**: .txt, .md, .pdf files
- **Real-time Feedback**: See upload progress and status

### 💬 Chat Interface
- **Ask Questions**: Type natural language questions about your documents
- **Source Attribution**: See which documents were used to answer your questions
- **Similarity Scores**: View relevance scores for each source
- **Conversation History**: Track your queries and responses

### 🕸️ Graph Visualization
- **Interactive Graph**: Explore your knowledge graph visually
- **Node Types**: 
  - 🟣 Purple: Documents
  - 🟣 Dark Purple: Communities
  - 🟢 Green: Entities
  - 🔵 Blue: Chunks
- **Hover Information**: See detailed info about nodes and edges
- **Zoom & Pan**: Navigate large graphs easily
- **Drag Nodes**: Rearrange the graph layout

### 📊 Live Statistics
- View real-time counts of documents, entities, chunks, and communities
- Track your knowledge base growth

### Workflow
1. **Upload Documents**: Drag files into the upload area
2. **Rebuild Graph**: Click "🔄 Rebuild Graph" to process documents and build the knowledge graph
3. **Explore Graph**: View the visual representation of your knowledge
4. **Ask Questions**: Use the chat to query your documents
5. **Refresh**: Update the graph visualization as needed

### Alternative: Manual Setup

If you prefer not to use Make:

1. Copy environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. Start services:
```bash
docker-compose build
docker-compose up -d
```

3. Check health:
```bash
curl http://localhost:8000/health
```

## Docker Deployment

### Quick Start with Makefile
```bash
make quickstart  # Initial setup
# Edit .env with your OPENAI_API_KEY and NEO4J_PASSWORD
make start       # Build and start everything
```

### Manual Docker Commands
```bash
cp .env.example .env
# Edit .env with your configuration
docker-compose build
docker-compose up -d
```

This starts:
- Neo4j graph database (ports 7474, 7687)
- Smart RAG API (port 8000)

### Useful Make Commands
```bash
make help        # Show all available commands
make status      # Check service status
make logs        # View logs
make stats       # Get graph statistics
make clean       # Stop and remove containers
```

## API Endpoints

### Web Interface

- `GET /` - Web-based chat and visualization interface

### Document Management

- `POST /api/v1/documents/upload` - Upload and process documents
- `GET /api/v1/documents/{doc_id}` - Get document details
- `DELETE /api/v1/documents/{doc_id}` - Delete document and associated graph

### Query

- `POST /api/v1/query` - Ask questions and get answers with sources
- `POST /api/v1/query/search` - Semantic search without LLM generation

### Graph Management

- `GET /api/v1/graph/stats` - Get graph statistics
- `GET /api/v1/graph/visualize` - Get graph data for visualization
- `POST /api/v1/graph/rebuild` - Rebuild hierarchical graph
- `GET /api/v1/graph/communities` - List detected communities

### Health

- `GET /health` - Health check endpoint

## API Documentation

Interactive API docs available at:
- **Web Interface**: `http://localhost:8000` (recommended)
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Neo4j Browser: `http://localhost:7474` (username: neo4j, password: from .env)

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
