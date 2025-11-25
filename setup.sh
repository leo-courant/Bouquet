#!/bin/bash
# Setup script for Smart RAG on Unix/macOS

set -e

echo "========================================"
echo "Smart RAG Setup Script"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3.11+ is required but not found"
    echo "Please install Python from https://www.python.org/"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo ""
fi

echo "UV found: $(uv --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
uv venv
echo ""

# Activate virtual environment and install dependencies
echo "Installing dependencies..."
source .venv/bin/activate
uv pip install -e .
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Please edit .env and add your:"
    echo "  - OPENAI_API_KEY"
    echo "  - NEO4J_PASSWORD"
    echo ""
else
    echo ".env file already exists"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p data/uploads
mkdir -p data/cache
mkdir -p logs
echo ""

echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Start Neo4j (docker-compose up -d neo4j OR install locally)"
echo "3. Run the application:"
echo "   - Activate environment: source .venv/bin/activate"
echo "   - Start server: uvicorn app.main:app --reload"
echo ""
echo "For full documentation, see README.md and QUICKSTART.md"
echo "========================================"
