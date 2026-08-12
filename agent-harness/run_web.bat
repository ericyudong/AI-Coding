@echo off
REM Agent Harness Web Console Launcher (Windows)
echo ============================================
echo   AGENT HARNESS // Web Control Console
echo ============================================
echo.

cd /d "%~dp0"

REM Install web dependencies if needed
pip install fastapi uvicorn[standard] websockets pyyaml rich -q 2>nul

echo Starting web server at http://localhost:8000
echo Press Ctrl+C to stop
echo.

python -m agent_harness.web.server

pause