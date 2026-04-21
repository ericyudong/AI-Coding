#!/bin/bash

# E-Claw Backend Run Script for Linux/Mac

echo "Starting E-Claw Backend..."

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
pip install -r requirements.txt

# Set environment variables
export DEBUG=True
export PORT=8000

# Run the application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload