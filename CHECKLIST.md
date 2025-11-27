# Getting Started Checklist

Use this checklist to get your Smart RAG system up and running.

## ✅ Pre-Deployment Checklist

### 1. Prerequisites Installed
- [ ] Python 3.11+ installed
- [ ] Docker and Docker Compose installed (for Docker deployment)
- [ ] Git installed (optional, for version control)
- [ ] OpenAI API key obtained from https://platform.openai.com/

### 2. Project Setup
- [ ] Project files are in place
- [ ] Navigate to project directory: `cd smart_rag`

### 3. Configuration

#### Option A: Using Docker (Recommended)
- [ ] Run setup: `make setup`
- [ ] Edit `.env` and set `OPENAI_API_KEY=your-actual-key`
- [ ] Edit `.env` and set `NEO4J_PASSWORD=your-secure-password`
- [ ] Note: The Neo4j password will be automatically picked up from `.env`

#### Option B: Local Development
- [ ] Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Unix) or use PowerShell script (Windows)
- [ ] Run setup: `make setup`
- [ ] Edit `.env` with your `OPENAI_API_KEY` and `NEO4J_PASSWORD`
- [ ] Start Neo4j: `make neo4j-start`

## 🚀 Deployment Checklist

### Docker Deployment
- [ ] Build images: `make build`
- [ ] Start services: `make up`
- [ ] Check services are running: `make status`
- [ ] View logs: `make logs` (or `make logs-app` for app only)
- [ ] Wait for services to be healthy (30-60 seconds)
- [ ] Test health endpoint: `make health`

### Local Deployment
- [ ] Ensure Neo4j is running: `make neo4j-start`
- [ ] Start application: `make dev`
- [ ] Test health endpoint: `make health`

### Quick Start (Everything in One Go)
- [ ] Run: `make quickstart` and follow the instructions
- [ ] Or run: `make start` to build and start everything

## 📝 Verification Checklist

### 1. API is Running
- [ ] Open browser to http://localhost:8000
- [ ] Should see: `{"name":"Smart RAG","version":"0.1.0","status":"running"}`
- [ ] Open http://localhost:8000/docs
- [ ] Should see interactive API documentation (Swagger UI)

### 2. Neo4j is Connected
- [ ] Open http://localhost:7474 (Neo4j Browser)
- [ ] Login with credentials (user: `neo4j`, password: your password)
- [ ] Should see Neo4j dashboard
- [ ] Run query: `RETURN "Connected!" as status`
- [ ] Should return success

### 3. OpenAI is Configured
- [ ] Check logs don't show OpenAI authentication errors
- [ ] Docker: `docker-compose logs app | grep -i openai`
- [ ] Local: Check terminal output

## 🧪 First Test Checklist

### 1. Upload a Test Document

Using API docs (http://localhost:8000/docs):
- [ ] Navigate to `POST /api/v1/documents/text`
- [ ] Click "Try it out"
- [ ] Enter test data:
  ```json
  {
    "title": "Test Document",
    "content": "Artificial intelligence is transforming technology. Machine learning enables computers to learn from data.",
    "source": "test"
  }
  ```
- [ ] Click "Execute"
- [ ] Should receive 200 response with document ID
- [ ] Copy the `document_id` for later

Alternatively, using curl:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/text" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Document",
    "content": "Artificial intelligence is transforming technology. Machine learning enables computers to learn from data.",
    "source": "test"
  }'
```

### 2. Build the Graph
- [ ] Navigate to `POST /api/v1/graph/rebuild` in API docs
- [ ] Click "Try it out" and "Execute"
- [ ] Should receive success response with level counts
- [ ] Wait for completion (check logs with `make logs-app`)

Or using curl:
```bash
curl -X POST "http://localhost:8000/api/v1/graph/rebuild"
```

### 3. Query the System
- [ ] Navigate to `POST /api/v1/query` in API docs
- [ ] Enter query:
  ```json
  {
    "query": "What is artificial intelligence?",
    "top_k": 5,
    "include_sources": true
  }
  ```
- [ ] Click "Execute"
- [ ] Should receive answer with sources
- [ ] Verify answer references the content

Or using curl:
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is artificial intelligence?",
    "top_k": 5,
    "include_sources": true
  }'
```

### 4. Check Graph Statistics
- [ ] Navigate to `GET /api/v1/graph/stats`
- [ ] Click "Execute"
- [ ] Should see node counts, edge counts, etc.
- [ ] Verify numbers > 0

Or using Makefile:
```bash
make stats
```

### 5. Explore in Neo4j Browser
- [ ] Open http://localhost:7474
- [ ] Run query: `MATCH (n) RETURN n LIMIT 25`
- [ ] Should see graph visualization
- [ ] Should see Document, Chunk, Entity nodes

## 📚 Load Sample Data Checklist (Optional)

### Using the init_db.py Script
- [ ] Run: `make init-db`
- [ ] Wait for completion (may take 2-3 minutes)
- [ ] Should see 3 documents processed
- [ ] Should see communities created
- [ ] Should see statistics displayed

### Verify Sample Data
- [ ] Check graph stats: `make stats`
- [ ] List documents: `curl http://localhost:8000/api/v1/documents`
- [ ] Should see 3 documents about AI/ML
- [ ] List communities: `curl http://localhost:8000/api/v1/graph/communities`
- [ ] Should see multiple communities

## 🧪 Run Tests Checklist (Optional)

### Setup for Testing
- [ ] Virtual environment will be created automatically

### Run Tests
- [ ] Run all tests: `make test`
- [ ] Should see tests passing

### Code Quality
- [ ] Format code: `make format`
- [ ] Lint code: `make lint`
- [ ] Type check: `make typecheck`
- [ ] Should have no errors

## 🔍 Troubleshooting Checklist

### If API Won't Start
- [ ] Check `.env` file exists and has correct values
- [ ] Verify OPENAI_API_KEY is set
- [ ] Check port 8000 is not already in use
- [ ] View logs for error messages
- [ ] Ensure Python 3.11+ is being used

### If Neo4j Connection Fails
- [ ] Verify Neo4j is running: `make status`
- [ ] Check NEO4J_PASSWORD is set in `.env` file
- [ ] Verify NEO4J_URI is correct (bolt://neo4j:7687 for Docker, bolt://localhost:7687 for local)
- [ ] Check Neo4j logs: `make logs-neo4j`
- [ ] Try restarting Neo4j: `make restart`

### If OpenAI Calls Fail
- [ ] Verify API key is valid at https://platform.openai.com/
- [ ] Check account has available credits
- [ ] Verify no rate limiting errors in logs
- [ ] Check internet connectivity
- [ ] Try a simple embedding test in API docs

### If Queries Return No Results
- [ ] Verify documents were uploaded successfully
- [ ] Check graph was built: `make stats`
- [ ] Verify chunks have embeddings (check Neo4j: `MATCH (c:Chunk) RETURN c.embedding IS NOT NULL`)
- [ ] Try rebuilding graph: `curl -X POST http://localhost:8000/api/v1/graph/rebuild`

### If Performance is Slow
- [ ] Reduce CHUNK_SIZE in .env
- [ ] Reduce TOP_K_RETRIEVAL in .env
- [ ] Check Docker resource limits
- [ ] Monitor Neo4j memory usage
- [ ] Check OpenAI API response times

## 📖 Next Steps Checklist

### Learn the System
- [ ] Read `README.md` - Overview
- [ ] Read `QUICKSTART.md` - Detailed guide
- [ ] Read `FEATURES.md` - Feature list
- [ ] Read `docs/ARCHITECTURE.md` - System design
- [ ] Read `docs/API_EXAMPLES.md` - More examples

### Customize Configuration
- [ ] Review all settings in `.env`
- [ ] Adjust chunk sizes for your documents
- [ ] Configure hierarchy depth
- [ ] Set appropriate top-K values
- [ ] Tune OpenAI model parameters

### Add Your Data
- [ ] Prepare your documents (text files)
- [ ] Upload via API or write a batch script
- [ ] Build the graph
- [ ] Test queries
- [ ] Iterate and refine

### Production Preparation
- [ ] Review `docs/DEPLOYMENT.md`
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Set up SSL/HTTPS
- [ ] Implement authentication
- [ ] Add rate limiting
- [ ] Set up log aggregation

## ✨ Success Criteria

You've successfully set up Smart RAG when:

- ✅ API responds at http://localhost:8000
- ✅ Interactive docs work at http://localhost:8000/docs
- ✅ Neo4j is accessible at http://localhost:7474
- ✅ Documents can be uploaded successfully
- ✅ Graph can be built and queried
- ✅ Queries return relevant answers with sources
- ✅ No errors in logs
- ✅ Graph statistics show expected data

## 🎉 Congratulations!

If you've checked all the boxes above, your Smart RAG system is up and running!

**You can now:**
- Upload your documents
- Build hierarchical knowledge graphs
- Ask questions and get intelligent answers
- Explore entity relationships
- Scale to production

**Happy RAG-ing! 🚀**
