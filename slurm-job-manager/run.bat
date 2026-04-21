@echo off
echo ========================================
echo Slurm作业管理系统启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 安装依赖...
pip install -r backend\requirements.txt

echo.
echo [2/3] 启动后端服务 (端口 8002)...
start "Slurm Backend" python backend\main.py

echo.
echo [3/3] 等待服务启动...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo 启动完成!
echo.
echo 后端API: http://localhost:8002
echo 前端页面: 请在浏览器中打开 frontend\index.html
echo.
echo 按任意键打开前端页面...
pause >nul

start frontend\index.html