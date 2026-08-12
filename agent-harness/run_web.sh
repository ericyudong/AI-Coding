#!/bin/bash
# Agent Harness Web Console Launcher (Linux/Mac)
echo "============================================"
echo "  AGENT HARNESS // Web Control Console"
echo "============================================"
echo ""

cd "$(dirname "$0")"

# Install web dependencies if needed
pip install fastapi "uvicorn[standard]" websockets pyyaml rich -q 2>/dev/null

echo "Starting web server at http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

python -m agent_harness.web.server