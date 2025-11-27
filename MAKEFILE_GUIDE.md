# Makefile Usage Guide

This project includes a comprehensive Makefile to simplify common tasks.

## Installing Make

If you don't have `make` installed:

### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install make
```

### macOS:
```bash
xcode-select --install
# or with Homebrew:
brew install make
```

### Windows:
Use WSL (Windows Subsystem for Linux) or install via:
- Chocolatey: `choco install make`
- Git Bash (comes with Git for Windows)

## Quick Reference

### Setup & Configuration
```bash
make setup          # Initial project setup (create .env from template)
make env-check      # Verify .env file exists and has required variables
```

### Docker Operations
```bash
make build          # Build Docker images
make up             # Start all services (neo4j + app)
make down           # Stop all services
make restart        # Restart all services
make logs           # View logs from all services
make logs-app       # View logs from app only
make logs-neo4j     # View logs from neo4j only
make status         # Show status of all services
```

### Database
```bash
make neo4j-start    # Start only Neo4j
make neo4j-stop     # Stop only Neo4j
make neo4j-shell    # Open Neo4j cypher-shell
make init-db        # Initialize database with sample data
```

### Health & Monitoring
```bash
make health         # Check API health endpoint
make stats          # Get graph statistics
```

### Development
```bash
make dev            # Run app locally (not in Docker)
make test           # Run test suite
make format         # Format code with black
make lint           # Run linter (ruff)
make typecheck      # Run type checker (mypy)
```

### Cleanup
```bash
make clean          # Stop services and remove containers
make clean-all      # Remove containers, volumes, and cached data
make clean-cache    # Remove cached data only
```

### Quick Start
```bash
make quickstart     # Complete setup from scratch
make start          # Build and start everything
```

## Common Workflows

### First Time Setup
```bash
make setup
# Edit .env with your OPENAI_API_KEY and NEO4J_PASSWORD
make build
make up
# Wait 60 seconds
make health
```

### Daily Development
```bash
make up             # Start services
make logs-app       # Watch logs
# Do your work
make down           # Stop when done
```

### Testing Changes
```bash
make dev            # Run locally for faster iteration
# or
make restart        # Restart Docker services
make logs-app       # Check logs
```

### Debugging Issues
```bash
make status         # Check what's running
make logs           # See all logs
make logs-neo4j     # Check database logs
make health         # Test API connectivity
```

## Without Make

If you prefer not to use Make, you can run Docker commands directly:

```bash
# Setup
cp .env.example .env
# Edit .env with your configuration

# Start
docker-compose build
docker-compose up -d

# Status
docker-compose ps

# Logs
docker-compose logs -f app

# Stop
docker-compose down

# Health check
curl http://localhost:8000/health

# Stats
curl -s http://localhost:8000/api/v1/graph/stats | python3 -m json.tool
```

## Tips

1. **Always run `make setup` first** - It creates the `.env` file and necessary directories
2. **Check `make status`** - Before running other commands to see what's already running
3. **Use `make help`** - To see all available commands with descriptions
4. **Use `make logs-app`** - Instead of `make logs` to avoid verbose Neo4j logs
5. **Run `make clean-all`** - If you need a fresh start (WARNING: deletes data)
