# Local Development Setup

## Overview

Your Bouquet app now runs **locally** for development, with only Neo4j in Docker. This means:

✅ **No rebuilding Docker images** when you change code  
✅ **Instant hot-reload** when you save files  
✅ **Direct access to logs** in your terminal  
✅ **Easy debugging** with your local Python tools  

## Quick Start

```bash
# Start everything (Neo4j + local app)
make dev
```

That's it! Your app is now running at **http://localhost:8000**

## What's Running Where

| Component | Location | Access |
|-----------|----------|--------|
| FastAPI App | **Local** (your machine) | http://localhost:8000 |
| Neo4j Database | **Docker** container | http://localhost:7474 |
| Static Files | **Local** (`static/` folder) | Served by FastAPI |

## Architecture

```
┌─────────────────────────────────────┐
│   Your Local Machine                │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  FastAPI App (Port 8000)    │  │
│   │  • app/                     │  │
│   │  • static/                  │  │
│   │  • Auto-reload enabled      │  │
│   └──────────┬──────────────────┘  │
│              │                      │
│              │ bolt://localhost:7687│
│              ▼                      │
│   ┌─────────────────────────────┐  │
│   │  Docker: Neo4j              │  │
│   │  • Graph Database           │  │
│   │  • Port 7474 (Browser)      │  │
│   │  • Port 7687 (Bolt)         │  │
│   └─────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Development Workflow

### 1. Start Development Server

```bash
make dev
```

This command:
1. Ensures `.env` file exists
2. Creates virtual environment if needed
3. Installs dependencies if needed
4. Starts Neo4j in Docker
5. Starts FastAPI with auto-reload

### 2. Make Code Changes

Edit any file in `app/` or `static/`:

```bash
# Edit Python code
nano app/api/graph.py

# Edit frontend
nano static/index.html
nano static/app.js
```

**The server automatically restarts** when you save!

### 3. View Changes

Just refresh your browser at http://localhost:8000

### 4. Stop Development

Press `Ctrl+C` in the terminal where the server is running.

Then stop Neo4j:

```bash
docker compose down
```

Or just:

```bash
make down
```

## File Changes - What Happens

| File Changed | What Happens | Reload Time |
|--------------|--------------|-------------|
| `app/**/*.py` | ✅ Auto-reload | ~1-2 seconds |
| `static/*.html` | ✅ Instant (refresh browser) | Immediate |
| `static/*.js` | ✅ Instant (refresh browser) | Immediate |
| `.env` | ⚠️ Restart needed | N/A |
| `pyproject.toml` | ⚠️ Reinstall deps | N/A |

## Common Commands

```bash
# Start development
make dev

# Stop Neo4j
make down

# Start only Neo4j
make neo4j-start

# Stop only Neo4j
make neo4j-stop

# View graph statistics
make stats

# Check health
make health

# Run tests
make test

# Format code
make format

# View all commands
make help
```

## Configuration

### .env File

Update `.env` for local development:

```bash
# Neo4j connection (localhost, not "neo4j" hostname)
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your-password-here

# OpenAI API
OPENAI_API_KEY=sk-...

# Development mode
APP_DEBUG=true
LOG_LEVEL=DEBUG
```

### Port Usage

| Port | Service | Can Change? |
|------|---------|-------------|
| 8000 | FastAPI | Yes (edit uvicorn command) |
| 7474 | Neo4j Browser | Yes (edit docker-compose.yml) |
| 7687 | Neo4j Bolt | Yes (edit docker-compose.yml) |

## Troubleshooting

### "Port 8000 already in use"

```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or kill all Docker containers
docker compose down
```

### "Permission denied" on logs/

```bash
# Fix permissions
chmod 755 logs/
rm -f logs/*.log
```

### "Neo4j connection failed"

```bash
# Check Neo4j is running
docker compose ps

# Start Neo4j
docker compose up -d neo4j

# Wait 10 seconds for it to be ready
sleep 10
```

### Changes not reflecting

```bash
# Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
# OR
# Clear browser cache
# OR
# Check terminal for errors
```

### "Module not found"

```bash
# Reinstall dependencies
source .venv/bin/activate
uv pip install -e .
```

## Advantages Over Docker

| Aspect | Local Dev | Full Docker |
|--------|-----------|-------------|
| Code changes | **Instant reload** | Rebuild image |
| Build time | **None** | 30-60 seconds |
| Debugging | **Easy** (local debugger) | Complex |
| Logs | **Terminal** | `docker logs` |
| File changes | **Immediate** | Need rebuild |
| Resource usage | **Lower** | Higher |
| Dependencies | **Local control** | Locked in image |

## When to Use Full Docker

Use full Docker (`make build && make up`) for:

- ✅ **Production deployment**
- ✅ **Testing the full stack** as deployed
- ✅ **Sharing with team** (consistent environment)
- ✅ **CI/CD pipelines**

Use local dev (`make dev`) for:

- ✅ **Active development**
- ✅ **Testing changes quickly**
- ✅ **Debugging issues**
- ✅ **Learning the codebase**

## Production Deployment

When ready to deploy, build the Docker image:

```bash
# Build production image
make build

# Test it works
make up

# Deploy to your server
docker compose -f docker-compose.yml up -d
```

## Tips & Tricks

### Auto-activate virtual environment

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Auto-activate venv when entering project
cd() {
    builtin cd "$@"
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
    fi
}
```

### VS Code Integration

Install the Python extension and set the interpreter:

1. Press `Ctrl+Shift+P`
2. Select "Python: Select Interpreter"
3. Choose `.venv/bin/python`

### Live Logs

Watch logs in real-time:

```bash
# Application logs
tail -f logs/smart_rag.log

# Neo4j logs
docker compose logs -f neo4j
```

### Quick Restart

```bash
# Just restart the app (Neo4j keeps running)
# Press Ctrl+C, then:
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Next Steps

1. **Start coding**: `make dev`
2. **Upload documents**: Open http://localhost:8000
3. **Make changes**: Edit files and see instant results
4. **Debug issues**: Check terminal for errors
5. **Test**: Run `make test` before committing

Happy coding! 🌸
