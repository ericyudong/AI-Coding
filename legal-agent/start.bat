@echo off
cd /d "%~dp0"
echo [1/2] Starting backend on http://127.0.0.1:8010 ...
start "legal-agent-backend" cmd /k "cd backend && .venv\Scripts\python run.py"
echo [2/2] Starting frontend on http://127.0.0.1:5173 ...
start "legal-agent-frontend" cmd /k "cd frontend && npm run dev"
echo.
echo Login URLs:
echo   Dev:  http://127.0.0.1:5173/login
echo   Prod: http://127.0.0.1:8010/login  (after npm run build + copy to backend/static)
echo Default account: admin / admin123
pause
