# Installation Notes

## Fixed: Build Configuration Issue

The `pyproject.toml` has been updated to correctly specify the package location. The error you encountered:

```
ValueError: Unable to determine which files to ship inside the wheel
```

Has been resolved by adding:

```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

This tells the build system that the `app` directory contains the Python package.

## Installation Process

When you run `uv pip install -e .`, the system will:

1. ✅ Build the `smart-rag` package (now works correctly)
2. 📥 Download and install dependencies (~2GB total):
   - FastAPI, Pydantic, Neo4j driver
   - LangChain and OpenAI libraries
   - **PyTorch** with CUDA support (~800MB)
   - **sentence-transformers** with dependencies
   - Various ML libraries (numpy, scikit-learn, networkx)
   - NVIDIA CUDA libraries (cublas, cudnn, etc.)

**Expected Time:** 5-10 minutes depending on your internet connection

## Using the Makefile

The Makefile has been updated to handle installation more efficiently:

### First Time Setup
```bash
# 1. Setup project (creates .env)
make setup

# 2. Edit .env with your credentials
nano .env  # or your preferred editor

# 3. Install dependencies (one-time, takes 5-10 min)
make install

# 4. For Docker deployment
make build
make up
```

### Development
```bash
# Run locally (installs deps if needed)
make dev

# Run tests (installs dev deps if needed)
make test

# Code quality tools
make format
make lint
make typecheck
```

## Installation Optimization

The Makefile now uses a marker file (`.venv/installed.marker`) to avoid reinstalling dependencies every time. Dependencies are only installed once unless:
- The `.venv` directory is deleted
- You run `make install` manually
- The marker file is deleted

## Large Dependencies

The sentence-transformers library pulls in PyTorch with CUDA support, which is why the installation is large. This is normal for ML/NLP applications.

If you want to reduce the installation size, you could:
1. Use CPU-only PyTorch (requires modifying dependencies)
2. Use OpenAI embeddings only (already configured)
3. Run everything in Docker (dependencies are in the container)

## Docker vs Local

### Docker (Recommended)
- ✅ No local Python dependencies needed
- ✅ Consistent environment
- ✅ Easier to manage
- ✅ Both Neo4j and app in containers

```bash
make setup
# Edit .env
make build
make up
```

### Local Development
- ⚠️ Requires installing ~2GB of dependencies
- ✅ Faster iteration during development
- ✅ Direct access to Python environment

```bash
make setup
# Edit .env
make install       # One-time, 5-10 minutes
make neo4j-start   # Start Neo4j in Docker
make dev           # Run app locally
```

## Troubleshooting

### If installation fails midway:
```bash
# Remove the virtual environment
rm -rf .venv

# Try again
make install
```

### If you get build errors:
```bash
# Make sure you have build tools
sudo apt-get update
sudo apt-get install build-essential python3-dev

# Try installing again
make install
```

### Check installation:
```bash
# Activate virtual environment
source .venv/bin/activate

# Check installed packages
uv pip list

# Try importing
python -c "import app; print('Success!')"
```

## Summary

✅ **Fixed:** `pyproject.toml` now correctly specifies package location  
✅ **Updated:** Makefile optimized to avoid repeated installations  
✅ **Recommended:** Use Docker for easiest setup  
✅ **Local Dev:** `make install` handles all dependencies  

You can now successfully run `uv pip install -e .` or use `make install`!
