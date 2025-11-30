# Smart RAG - Makefile
# =====================================================
# Convenient commands for managing the Smart RAG project
# =====================================================

.PHONY: help setup build up down restart logs status clean clean-all test format lint env-check health init-db

# Default target - show help

# help: Print this help message listing common make commands and usage notes
help:
	@echo "Smart RAG - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup & Configuration:"
	@echo "  make setup          - Initial project setup (create .env from template)"
	@echo "  make env-check      - Verify .env file exists and has required variables"
	@echo "  make install        - Install Python dependencies (may take several minutes)"
	@echo ""
	@echo "Docker Operations:"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start all services (neo4j + app)"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs from all services"
	@echo "  make logs-app       - View logs from app only"
	@echo "  make logs-neo4j     - View logs from neo4j only"
	@echo "  make status         - Show status of all services"
	@echo ""
	@echo "Database:"
	@echo "  make neo4j-start    - Start only Neo4j"
	@echo "  make neo4j-stop     - Stop only Neo4j"
	@echo "  make neo4j-shell    - Open Neo4j cypher-shell"
	@echo "  make init-db        - Initialize database with sample data"
	@echo ""
	@echo "Health & Monitoring:"
	@echo "  make health         - Check API health endpoint"
	@echo "  make stats          - Get graph statistics"
	@echo ""
	@echo "Development:"
	@echo "  make dev            - Run app locally (not in Docker)"
	@echo "  make test           - Run test suite"
	@echo "  make format         - Format code with black"
	@echo "  make lint           - Run linter (ruff)"
	@echo "  make typecheck      - Run type checker (mypy)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Stop services and remove containers"
	@echo "  make clean-all      - Remove containers, volumes, and cached data"
	@echo "  make clean-cache    - Remove cached data only"
	@echo ""

# =====================================================
# Setup & Configuration
# =====================================================


# setup: Create a local `.env` from the example and ensure data/log directories exist
setup: env-check
	@echo "Setting up Smart RAG..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file from .env.example"; \
		echo ""; \
		echo "IMPORTANT: Edit .env and set:"; \
		echo "  1. OPENAI_API_KEY=your-actual-api-key"; \
		echo "  2. NEO4J_PASSWORD=your-secure-password"; \
		echo ""; \
	else \
		echo "✓ .env file already exists"; \
	fi
	@mkdir -p data/uploads data/cache logs
	@echo "✓ Created data directories"
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your configuration"
	@echo "  2. Run: make build"
	@echo "  3. Run: make up"


# env-check: Ensure required `.env.example` exists before other setup/build steps
env-check:
	@if [ ! -f .env.example ]; then \
		echo "ERROR: .env.example not found!"; \
		exit 1; \
	fi


# install: Create venv (if missing) and install Python dependencies into it
install:
	@echo "Installing Python dependencies..."
	@echo "Note: This will download ~2GB of dependencies (PyTorch, CUDA libraries, etc.)"
	@echo "This may take 5-10 minutes depending on your internet connection."
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@echo "Installing packages..."
	uv pip install -e .
	@touch .venv/installed.marker
	@echo "✓ Dependencies installed successfully!"

# =====================================================
# Docker Operations
# =====================================================


# build: Build the project's Docker images using `docker compose build`
build: env-check
	@echo "Building Docker images..."
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	docker compose build


# up: Start all Docker services (app + neo4j) in detached mode
up: env-check
	@echo "Starting all services..."
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@docker compose down 2>/dev/null || true
	docker compose up -d
	@echo ""
	@echo "✓ Services started!"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - Neo4j Browser: http://localhost:7474"
	@echo ""
	@echo "Wait 30-60 seconds for services to initialize, then run:"
	@echo "  make health"


# down: Stop and remove running Docker services
down:
	@echo "Stopping all services..."
	docker compose down
	@echo "✓ Services stopped"


# restart: Restart running Docker services
restart:
	@echo "Restarting all services..."
	docker compose restart
	@echo "✓ Services restarted"


# logs: Follow logs for all Docker services
logs:
	docker compose logs -f


# logs-app: Follow logs for the application service only
logs-app:
	docker compose logs -f app


# logs-neo4j: Follow logs for the Neo4j service only
logs-neo4j:
	docker compose logs -f neo4j


# status: Show running status of all configured Docker services
status:
	@echo "Service Status:"
	@echo "==============="
	docker compose ps

# =====================================================
# Neo4j Database
# =====================================================


# neo4j-start: Start only the Neo4j Docker service (useful for local dev)
neo4j-start: env-check
	@echo "Starting Neo4j..."
	@docker compose down neo4j 2>/dev/null || true
	docker compose up -d neo4j
	@echo "Waiting for Neo4j to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12; do \
		if docker compose exec -T neo4j cypher-shell -u neo4j -p "$$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; then \
			echo "✓ Neo4j is ready!"; \
			break; \
		fi; \
		echo "  Waiting for Neo4j... ($$i/12)"; \
		sleep 5; \
	done
	@echo "  - Browser: http://localhost:7474"
	@echo "  - Bolt: bolt://localhost:7687"


# neo4j-stop: Stop the Neo4j Docker container
neo4j-stop:
	@echo "Stopping Neo4j..."
	docker compose stop neo4j
	@echo "✓ Neo4j stopped"


# neo4j-shell: Open an interactive cypher-shell on the Neo4j container
neo4j-shell:
	@echo "Opening Neo4j cypher-shell..."
	@echo "Note: You'll need to enter the password from your .env file"
	@docker compose exec neo4j cypher-shell -u neo4j


# init-db: Run the initialization script inside the app container to seed sample data
init-db:
	@echo "Initializing database with sample data..."
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "This will run the init_db.py script..."
	docker compose exec app python scripts/init_db.py || \
		(echo "Note: Run this after services are up with 'make up'" && exit 1)

# =====================================================
# Health & Monitoring
# =====================================================


# health: Query the API health endpoint and pretty-print the JSON result
health:
	@echo "Checking API health..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || \
		echo "ERROR: API not responding. Check if services are running with 'make status'"


# stats: Fetch graph statistics from the API and pretty-print the result
stats:
	@echo "Getting graph statistics..."
	@curl -s http://localhost:8000/api/v1/graph/stats | python3 -m json.tool || \
		echo "ERROR: API not responding. Check if services are running with 'make status'"

# =====================================================
# Development
# =====================================================


# dev: Start Neo4j in Docker and run the app locally with uvicorn and auto-reload
dev: env-check
	@echo "Running app locally (development mode)..."
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@if [ ! -f .venv/installed.marker ]; then \
		echo "Installing dependencies (this may take a few minutes)..."; \
		uv pip install -e .; \
		touch .venv/installed.marker; \
	fi
	@echo "Starting Neo4j in Docker..."
	@docker compose down neo4j 2>/dev/null || true
	@docker compose up -d neo4j
	@echo "Waiting for Neo4j to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12; do \
		if docker compose exec -T neo4j cypher-shell -u neo4j -p "$$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; then \
			echo "✓ Neo4j is ready!"; \
			break; \
		fi; \
		echo "  Waiting for Neo4j... ($$i/12)"; \
		sleep 5; \
	done
	@echo ""
	@echo "✓ Neo4j started at http://localhost:7474"
	@echo "✓ Starting development server with auto-reload..."
	@echo ""
	@. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


# test: Ensure virtualenv exists and run the project's pytest suite
test:
	@echo "Running tests..."
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@if [ ! -f .venv/installed.marker ]; then \
		echo "Installing dev dependencies (this may take a few minutes)..."; \
		uv pip install -e \".[dev]\"; \
		touch .venv/installed.marker; \
	fi
	uv run pytest


# format: Run `black` to format the codebase (installs dev deps if needed)
format:
	@echo "Formatting code with black..."
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@if [ ! -f .venv/installed.marker ]; then \
		echo "Installing dev dependencies..."; \
		uv pip install -e \".[dev]\"; \
		touch .venv/installed.marker; \
	fi
	uv run black .
	@echo "✓ Code formatted"


# lint: Run `ruff` linter on the repository (installs dev deps if missing)
lint:
	@echo "Running linter (ruff)..."
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@if [ ! -f .venv/installed.marker ]; then \
		echo "Installing dev dependencies..."; \
		uv pip install -e \".[dev]\"; \
		touch .venv/installed.marker; \
	fi
	uv run ruff check .


# typecheck: Run `mypy` for static type checking (installs dev deps if needed)
typecheck:
	@echo "Running type checker (mypy)..."
	@if [ ! -d .venv ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@if [ ! -f .venv/installed.marker ]; then \
		echo "Installing dev dependencies..."; \
		uv pip install -e \".[dev]\"; \
		touch .venv/installed.marker; \
	fi
	uv run mypy app/

# =====================================================
# Cleanup
# =====================================================


# clean: Stop services and remove containers (doesn't remove volumes/data)
clean:
	@echo "Cleaning up (removing containers)..."
	docker compose down
	@echo "✓ Containers removed"


# clean-all: Destructive cleanup - removes containers, volumes, and cached data
clean-all:
	@echo "WARNING: This will remove all containers, volumes, and cached data!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@echo "Removing containers and volumes..."
	@docker compose down -v
	@echo "Removing cached data..."
	rm -rf data/cache/* data/uploads/* logs/*
	@echo "✓ Complete cleanup finished"


# clean-cache: Remove generated cache and uploaded files (non-destructive)
clean-cache:
	@echo "Removing cached data..."
	rm -rf data/cache/* data/uploads/*
	@echo "✓ Cache cleaned"

# =====================================================
# Quick Start Commands
# =====================================================

# Complete setup from scratch

# quickstart: Convenience target that runs `setup` and prints basic first steps
quickstart: setup
	@echo ""
	@echo "Quick Start Guide:"
	@echo "=================="
	@echo "1. Edit .env with your OPENAI_API_KEY and NEO4J_PASSWORD"
	@echo "2. Run: make build"
	@echo "3. Run: make up"
	@echo "4. Wait 60 seconds, then run: make health"
	@echo "5. Visit: http://localhost:8000/docs"

# Build and start everything

# start: Build and start everything (shorthand for `make build && make up`)
start: build up
	@echo "Waiting for services to be healthy..."
	@sleep 30
	@make health
