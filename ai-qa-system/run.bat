@echo off
REM AI Q&A System Startup Script for Windows

echo Starting AI Q&A System...

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install dependencies if needed
if not exist "venv\Lib\site-packages\fastapi" (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if .env exists
if not exist ".env" (
    echo Creating .env file from example...
    copy .env.example .env
    echo Please configure your .env file with API keys!
    notepad .env
)

REM Start the server
echo Starting server at http://localhost:8000
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

pause