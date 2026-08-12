@echo off
REM Agent Harness Framework - Windows Startup Script

echo ============================================
echo Agent Harness Framework
echo ============================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Running examples...
echo.

REM Run the selected example
if "%1"=="basic" (
    python examples/basic_agent.py
) else if "%1"=="memory" (
    python examples/memory_demo.py
) else if "%1"=="evolution" (
    python examples/evolution_demo.py
) else if "%1"=="test" (
    python -m pytest tests/ -v
) else (
    echo Usage: run.bat [basic^|memory^|evolution^|test]
    echo.
    echo Examples:
    echo   run.bat basic      - Run basic agent example
    echo   run.bat memory     - Run memory management demo
    echo   run.bat evolution  - Run self-evolution demo
    echo   run.bat test       - Run tests
)

pause