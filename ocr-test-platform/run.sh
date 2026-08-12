#!/bin/bash

echo "========================================"
echo "        OCR测试平台 启动脚本"
echo "========================================"
echo ""

cd "$(dirname "$0")/backend"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查依赖是否安装
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "[信息] 首次运行，正在安装依赖..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖安装失败"
        exit 1
    fi
fi

echo ""
echo "[信息] 正在启动OCR测试平台..."
echo "[信息] 访问地址: http://localhost:8000"
echo "[信息] API文档: http://localhost:8000/docs"
echo "[信息] 按 Ctrl+C 停止服务"
echo ""

python3 main.py