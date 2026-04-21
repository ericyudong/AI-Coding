@echo off
chcp 65001 >nul
echo Starting E-Claw Backend...
cd /d C:\eswin\emaas\AI-Coding\e-claw\backend
call venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause