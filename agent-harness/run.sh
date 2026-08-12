#!/bin/bash
# Agent Harness Framework - Linux/Mac Startup Script

echo "============================================"
echo "Agent Harness Framework"
echo "============================================"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "Running examples..."
echo ""

# Run the selected example
case "$1" in
    basic)
        python examples/basic_agent.py
        ;;
    memory)
        python examples/memory_demo.py
        ;;
    evolution)
        python examples/evolution_demo.py
        ;;
    test)
        python -m pytest tests/ -v
        ;;
    *)
        echo "Usage: ./run.sh [basic|memory|evolution|test]"
        echo ""
        echo "Examples:"
        echo "  ./run.sh basic      - Run basic agent example"
        echo "  ./run.sh memory     - Run memory management demo"
        echo "  ./run.sh evolution  - Run self-evolution demo"
        echo "  ./run.sh test       - Run tests"
        ;;
esac