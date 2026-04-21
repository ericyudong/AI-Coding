#!/bin/bash
# DeepSeek Q&A System - Docker Compose launcher

echo ""
echo "========================================="
echo "   DeepSeek Q&A System Docker Launcher"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker from https://www.docker.com/"
    exit 1
fi

echo "✅ Docker found:"
docker --version
echo ""

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed"
    echo "Please install Docker Compose"
    exit 1
fi

echo "✅ Docker Compose found:"
docker-compose --version
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Please create a .env file with your DeepSeek API key:"
    echo ""
    echo "  1. Copy .env.example to .env"
    echo "  2. Add your actual API key: DEEPSEEK_API_KEY=your_key_here"
    echo ""
    read -p "Press Enter to continue..."
fi

# Start Docker Compose
echo ""
echo "========================================="
echo "   Starting with Docker Compose"
echo "========================================="
echo ""
echo "🚀 Application will start on http://localhost:8000"
echo "📖 API documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

docker-compose up
