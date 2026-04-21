#!/bin/bash
# AI Agent 模型管理系统 - Unix启动脚本
# 使用: ./run.sh 或 bash run.sh

set -e

echo ""
echo "========================================================"
echo "AI Agent Model Management System"
echo "Unix Launcher"
echo "========================================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed"
    echo "Please install Python 3.9+ using:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu: sudo apt install python3.11 python3-pip"
    exit 1
fi

# 获取Python版本
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "[INFO] Python version: $PYTHON_VERSION"

# 检查是否需要创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        exit 1
    fi
fi

# 激活虚拟环境
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# 检查依赖是否已安装
if ! pip list | grep -q torch; then
    echo "[INFO] Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies"
        exit 1
    fi
fi

# 运行主程序
echo ""
echo "[INFO] Starting AI Agent System..."
echo ""
python main.py

exit $?
