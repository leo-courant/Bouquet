# Quick Start Guide

## Installation

### Option 1: Docker (Recommended)

**Prerequisites**: Docker and Docker Compose installed

1. **Configure environment**:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

2. **Update Neo4j password** in `docker-compose.yml`:
```yaml
NEO4J_AUTH=neo4j/your-secure-password
```

Also update in `.env`:
```env
NEO4J_PASSWORD=your-secure-password
```

3. **Start services**:
```bash
docker-compose up -d
```

4. **Verify**:
```bash
# Check services are running
docker-compose ps

# Check application logs
docker-compose logs -f app

# Test health endpoint
curl http://localhost:8000/health
```

5. **Access the application**:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (user: neo4j, password: your-password)

### Option 2: Local Development

**Prerequisites**: Python 3.11+, Neo4j 5.14+, UV package manager

1. **Install UV**:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. **Setup Python environment**:
```bash
# Create virtual environment
uv venv

# Activate (Unix/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

3. **Install and start Neo4j**:
- Download from https://neo4j.com/download/
- Follow installation instructions
- Start Neo4j and set password

4. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your settings:
# - OPENAI_API_KEY
# - NEO4J_PASSWORD
```

5. **Run the application**:
```bash
# Development mode with auto-reload
uv run uvicorn app.main:app --reload

# Or use Python directly
python -m uvicorn app.main:app --reload
```

6. **Access**:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

## First Steps

### 1. Upload Your First Document

**Using the API docs** (http://localhost:8000/docs):
1. Navigate to POST `/api/v1/documents/text`
2. Click "Try it out"
3. Enter:
   ```json
   {
     "title": "My First Document",
     "content": "Artificial Intelligence is transforming technology...",
     "source": "manual"
   }
   ```
4. Click "Execute"

**Using curl**:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/text" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Document",
    "content": "Artificial Intelligence is transforming technology. Machine learning enables computers to learn from data without explicit programming.",
    "source": "manual"
  }'
```

### 2. Build the Graph

After uploading documents, build the hierarchical graph structure:

```bash
curl -X POST "http://localhost:8000/api/v1/graph/rebuild"
```

### 3. Query the System

Ask questions about your documents:

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is artificial intelligence?",
    "top_k": 5,
    "include_sources": true
  }'
```

### 4. Explore the Graph

**View statistics**:
```bash
curl http://localhost:8000/api/v1/graph/stats
```

**List communities**:
```bash
curl http://localhost:8000/api/v1/graph/communities
```

**Browse in Neo4j**:
1. Open http://localhost:7474
2. Login with credentials
3. Run query: `MATCH (n) RETURN n LIMIT 25`

## Using the Example Scripts

### Initialize with Sample Data

```bash
# Activate virtual environment if not already active
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate  # Windows

# Run initialization script
python scripts/init_db.py
```

This will:
- Load 3 sample documents about AI/ML
- Process and create knowledge graph
- Build hierarchical communities
- Display statistics

### Run Example Usage

```bash
python scripts/example_usage.py
```

This demonstrates:
- Document processing
- Graph building
- Querying
- Statistics retrieval

## Common Tasks

### Upload a File

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@path/to/your/document.txt" \
  -F "title=Optional Custom Title"
```

### Search Without Generating Answer

```bash
curl -X POST "http://localhost:8000/api/v1/query/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "top_k": 10
  }'
```

### Get Related Entities

```bash
curl "http://localhost:8000/api/v1/query/entities/Machine%20Learning/related?max_hops=2"
```

### List Documents

```bash
curl "http://localhost:8000/api/v1/documents?limit=50"
```

### Delete a Document

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/{document-id}"
```

## Stopping Services

### Docker

```bash
# Stop services
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v
```

### Local Development

```bash
# Stop application (Ctrl+C in terminal)

# Stop Neo4j
neo4j stop
```

## Next Steps

1. **Read the documentation**:
   - [Architecture](docs/ARCHITECTURE.md)
   - [API Examples](docs/API_EXAMPLES.md)
   - [Deployment Guide](docs/DEPLOYMENT.md)

2. **Explore the API**:
   - Interactive docs at http://localhost:8000/docs
   - Alternative docs at http://localhost:8000/redoc

3. **Customize configuration**:
   - Edit `.env` for your needs
   - Adjust chunk sizes, model settings, etc.

4. **Add your data**:
   - Upload your documents
   - Build your knowledge graph
   - Start querying!

## Troubleshooting

### "Connection refused" to Neo4j
- Ensure Neo4j is running: `docker-compose ps` or `neo4j status`
- Check credentials in `.env` match Neo4j configuration

### OpenAI API errors
- Verify `OPENAI_API_KEY` is set correctly in `.env`
- Check your OpenAI account has available credits
- Ensure API key has proper permissions

### Application won't start
- Check all required environment variables are set
- View logs: `docker-compose logs app` or check terminal output
- Ensure ports 8000 and 7687 are not in use

### Out of memory
- Reduce `CHUNK_SIZE` in `.env`
- Increase Docker memory limits
- Process fewer documents at once

## Getting Help

- **Documentation**: Check the `docs/` folder
- **API Docs**: http://localhost:8000/docs
- **Logs**: `docker-compose logs -f` or `logs/smart_rag.log`
- **Neo4j Browser**: http://localhost:7474 for graph visualization

## Development

### Run tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=app
```

### Code formatting

```bash
# Format code
black .

# Lint
ruff check .

# Type checking
mypy app/
```
