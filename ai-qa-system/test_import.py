#!/usr/bin/env python
"""Test script for AI Q&A System."""
import sys
sys.path.insert(0, '.')

print("Testing AI Q&A System imports...")

# Test config
print("1. Testing config...")
from backend.config import settings
print(f"   Config loaded - LLM Provider: {settings.llm_provider}")

# Test models
print("2. Testing models...")
from backend.models import ChatRequest, ChatResponse, HealthResponse
print("   Models loaded successfully")

# Test session service directly (avoid LLM service which needs API key)
print("3. Testing session service...")
import importlib
session_module = importlib.import_module('backend.services.session_service')
SessionManager = session_module.SessionManager
session_mgr = SessionManager()
session_id = session_mgr.create_session()
print(f"   Session service working, created session: {session_id[:8]}...")

print("\n✅ All basic imports successful!")
print("\nTo run the full system:")
print("1. Configure your API key in .env file")
print("2. Install: pip install -r requirements.txt")
print("3. Run: python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000")
print("4. Open: http://localhost:8000")
