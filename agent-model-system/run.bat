@echo off
REM AI Agent 模型管理系统 - Windows启动脚本
REM 使用: run.bat

echo.
echo ========================================================
echo AI Agent Model Management System
echo Windows Launcher
echo ========================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

REM 检查是否需要创建虚拟环境
if not exist "venv\" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM 激活虚拟环境
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM 检查依赖是否已安装
pip list | find "torch" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

REM 运行主程序
echo.
echo [INFO] Starting AI Agent System...
echo.
python main.py

REM 保持窗口打开以显示任何错误
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with error code %errorlevel%
    pause
)

exit /b %errorlevel%
