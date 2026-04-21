#!/bin/bash
# DeepSeek Q&A System - Quick Start Script for macOS/Linux

echo ""
echo "========================================"
echo "   DeepSeek Q&A System Launcher"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

echo "✅ Python found:"
python3 --version
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  WARNING: .env file not found!"
    echo "Please create a .env file with your DeepSeek API key:"
    echo ""
    echo "  1. Copy .env.example to .env"
    echo "  2. Add your actual API key: DEEPSEEK_API_KEY=your_key_here"
    echo ""
    read -p "Press Enter to continue..."
fi

# Start the backend
echo ""
echo "========================================"
echo "   Starting Backend Server"
echo "========================================"
echo ""
echo "🚀 Backend will start on http://localhost:8000"
echo "📖 API documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
