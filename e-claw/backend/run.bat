@echo off
REM E-Claw Backend Run Script for Windows

echo Starting E-Claw Backend...

cd /d %~dp0

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -r requirements.txt

REM Set environment variables
set DEBUG=True
set PORT=8000
set KUBECONFIG=C:\Users\E0008090\.minikube\config

REM Run the application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause