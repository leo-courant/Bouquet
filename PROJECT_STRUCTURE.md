# Project Structure

```
smart_rag/
│
├── app/                                  # Main application package
│   ├── __init__.py                      # Package initialization
│   ├── main.py                          # FastAPI application entry point
│   │
│   ├── api/                             # API endpoints
│   │   ├── __init__.py                  # API router aggregation
│   │   ├── documents.py                 # Document management endpoints
│   │   ├── query.py                     # Query and search endpoints
│   │   └── graph.py                     # Graph management endpoints
│   │
│   ├── core/                            # Core configuration and dependencies
│   │   ├── __init__.py                  # Core exports
│   │   ├── config.py                    # Settings and configuration
│   │   ├── logging.py                   # Logging setup
│   │   └── dependencies.py              # Dependency injection
│   │
│   ├── domain/                          # Domain models (Pydantic)
│   │   ├── __init__.py                  # Domain exports
│   │   ├── models.py                    # Document, Chunk, Entity, Relationship
│   │   ├── graph.py                     # GraphNode, GraphEdge, Community, GraphStats
│   │   └── query.py                     # QueryRequest, QueryResponse, SearchResult
│   │
│   ├── repositories/                    # Data access layer
│   │   ├── __init__.py                  # Repository exports
│   │   └── neo4j_repository.py          # Neo4j database operations
│   │
│   └── services/                        # Business logic services
│       ├── __init__.py                  # Service exports
│       ├── embedding_service.py         # OpenAI embedding generation
│       ├── entity_extractor.py          # LLM-based entity extraction
│       ├── document_processor.py        # Document chunking and processing
│       ├── graph_builder.py             # Hierarchical graph construction
│       └── query_engine.py              # RAG query and retrieval
│
├── tests/                               # Test suite
│   ├── __init__.py                      # Tests package
│   ├── conftest.py                      # Pytest configuration and fixtures
│   ├── test_embedding_service.py        # Embedding service tests
│   └── test_document_processor.py       # Document processor tests
│
├── scripts/                             # Utility scripts
│   ├── example_usage.py                 # Example usage demonstration
│   └── init_db.py                       # Database initialization script
│
├── data/                                # Data storage
│   ├── uploads/                         # Uploaded documents
│   │   └── .gitkeep                     # Git placeholder
│   └── cache/                           # Cached data
│       └── .gitkeep                     # Git placeholder
│
├── docs/                                # Documentation
│   ├── API_EXAMPLES.md                  # API usage examples
│   ├── ARCHITECTURE.md                  # System architecture overview
│   └── DEPLOYMENT.md                    # Deployment guide
│
├── logs/                                # Application logs (auto-created)
│   └── smart_rag.log                    # Main log file (rotated)
│
├── .env.example                         # Environment variables template
├── .gitignore                           # Git ignore rules
├── docker-compose.yml                   # Docker Compose configuration
├── Dockerfile                           # Docker image definition
├── FEATURES.md                          # Feature overview
├── LICENSE                              # MIT License
├── pyproject.toml                       # Python project configuration (UV)
├── QUICKSTART.md                        # Quick start guide
├── README.md                            # Main documentation
├── setup.bat                            # Windows setup script
└── setup.sh                             # Unix/macOS setup script
```

## Directory Descriptions

### `/app` - Main Application
The core application code following clean architecture principles:

- **api/**: REST API endpoints organized by resource
- **core/**: Configuration, logging, and dependency injection
- **domain/**: Business entities and data models (Pydantic)
- **repositories/**: Data access abstractions (Neo4j)
- **services/**: Business logic and orchestration

### `/tests` - Test Suite
Pytest-based test suite with fixtures and unit tests:

- Unit tests for services
- Integration tests for API endpoints
- Mock fixtures for external dependencies

### `/scripts` - Utility Scripts
Helper scripts for common operations:

- Database initialization with sample data
- Example usage demonstrations
- Maintenance and migration scripts

### `/data` - Data Storage
Runtime data storage directories:

- **uploads/**: Temporarily stores uploaded documents
- **cache/**: Caches embeddings and computed results

### `/docs` - Documentation
Comprehensive documentation:

- **API_EXAMPLES.md**: cURL and code examples
- **ARCHITECTURE.md**: System design and architecture
- **DEPLOYMENT.md**: Production deployment guide

### `/logs` - Application Logs
Auto-generated log files:

- Rotating log files (7 days retention)
- JSON-structured logging for parsing
- Console and file outputs

## Key Files

### Configuration Files

- **pyproject.toml**: Python project metadata, dependencies (managed by UV)
- **.env.example**: Template for environment variables
- **docker-compose.yml**: Multi-container Docker setup
- **Dockerfile**: Application container image

### Documentation Files

- **README.md**: Main project overview and getting started
- **QUICKSTART.md**: Step-by-step quick start guide
- **FEATURES.md**: Complete feature overview
- **LICENSE**: MIT License

### Setup Scripts

- **setup.sh**: Automated setup for Unix/macOS
- **setup.bat**: Automated setup for Windows

## Module Organization

### Layered Architecture

```
┌─────────────────────────────────────┐
│         API Layer (FastAPI)         │  ← HTTP endpoints
├─────────────────────────────────────┤
│      Service Layer (Business)       │  ← Business logic
├─────────────────────────────────────┤
│     Repository Layer (Data)         │  ← Data access
├─────────────────────────────────────┤
│      Domain Layer (Models)          │  ← Data models
└─────────────────────────────────────┘
```

### Dependency Flow

```
API ──depends on──> Services ──depends on──> Repositories
 │                       │                         │
 └──uses──> Domain <────┘                         │
                  │                                │
                  └────────────uses────────────────┘
```

## Import Conventions

```python
# From domain (data models)
from app.domain import Document, Chunk, Entity, QueryRequest

# From services (business logic)
from app.services import DocumentProcessor, QueryEngine

# From repositories (data access)
from app.repositories import Neo4jRepository

# From core (configuration)
from app.core import get_settings, get_neo4j_repository
```

## File Naming Conventions

- **Python files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

## Code Organization Principles

1. **Separation of Concerns**: Each module has a single responsibility
2. **Dependency Injection**: Services injected via FastAPI dependencies
3. **Type Safety**: Full type hints with mypy checking
4. **Async First**: Async/await throughout for I/O operations
5. **Error Handling**: Comprehensive exception handling at all layers
6. **Logging**: Structured logging with context
7. **Testing**: Unit tests alongside code, fixtures in conftest.py
8. **Documentation**: Docstrings for all public interfaces

## Adding New Features

### New API Endpoint
1. Add endpoint function in `app/api/{resource}.py`
2. Use dependency injection for services
3. Add response models in `app/domain/`
4. Update API router in `app/api/__init__.py`

### New Service
1. Create service class in `app/services/{service_name}.py`
2. Add dependency function in `app/core/dependencies.py`
3. Export from `app/services/__init__.py`
4. Add tests in `tests/test_{service_name}.py`

### New Domain Model
1. Create Pydantic model in `app/domain/{category}.py`
2. Export from `app/domain/__init__.py`
3. Use in services and API layers

### New Repository Method
1. Add method to `Neo4jRepository` class
2. Write Cypher query
3. Add error handling
4. Document with docstring
