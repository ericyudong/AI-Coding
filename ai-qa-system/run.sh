#!/bin/bash
# AI Q&A System Startup Script for Linux/Mac

echo "Starting AI Q&A System..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please configure your .env file with API keys!"
    echo " nano .env"
fi

# Start the server
echo "Starting server at http://localhost:8000"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000