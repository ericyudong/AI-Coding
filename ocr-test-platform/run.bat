@echo off
chcp 65001 >nul
title OCR测试平台

echo ========================================
echo        OCR测试平台 启动脚本
echo ========================================
echo.

cd /d "%~dp0backend"

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖是否安装
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [信息] 首次运行，正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [信息] 正在启动OCR测试平台...
echo [信息] 访问地址: http://localhost:8000
echo [信息] API文档: http://localhost:8000/docs
echo [信息] 按 Ctrl+C 停止服务
echo.

python main.py

pause