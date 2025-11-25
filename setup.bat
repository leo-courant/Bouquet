@echo off
REM Setup script for Smart RAG on Windows

echo ========================================
echo Smart RAG Setup Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11+ is required but not found
    echo Please install Python from https://www.python.org/
    exit /b 1
)

REM Check if UV is installed
uv --version >nul 2>&1
if errorlevel 1 (
    echo Installing UV package manager...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
)

REM Create virtual environment
echo Creating virtual environment...
uv venv
echo.

REM Activate virtual environment and install dependencies
echo Installing dependencies...
call .venv\Scripts\activate
uv pip install -e .
echo.

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env and add your:
    echo   - OPENAI_API_KEY
    echo   - NEO4J_PASSWORD
    echo.
) else (
    echo .env file already exists
)

REM Create data directories
echo Creating data directories...
if not exist data\uploads mkdir data\uploads
if not exist data\cache mkdir data\cache
if not exist logs mkdir logs
echo.

echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your API keys
echo 2. Start Neo4j (docker-compose up -d neo4j OR install locally)
echo 3. Run the application:
echo    - Activate environment: .venv\Scripts\activate
echo    - Start server: uvicorn app.main:app --reload
echo.
echo For full documentation, see README.md and QUICKSTART.md
echo ========================================

pause
