@echo off
cd /d C:\eswin\emaas\AI-Coding\e-claw\backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause