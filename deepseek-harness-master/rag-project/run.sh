#!/usr/bin/env bash
# Start both FastAPI backend and Streamlit frontend.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting RAG Backend (FastAPI on :8000)..."
uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

echo "🎨 Starting RAG Frontend (Streamlit on :8501)..."
streamlit run frontend/app.py --server.port 8501 --server.headless true &
FRONTEND_PID=$!

echo ""
echo "✅ Backend:  http://127.0.0.1:8000/docs"
echo "✅ Frontend: http://127.0.0.1:8501"
echo ""
echo "Press Ctrl+C to stop both services."

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

wait
