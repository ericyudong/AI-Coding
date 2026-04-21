# 📥 详细安装指南

本文档提供了详细的安装和配置步骤。

## 系统要求

### 硬件要求

| 配置项 | 最低要求 | 推荐 | 高性能 |
|-------|---------|-----|--------|
| CPU | 4核 | 8核 | 16核+ |
| RAM | 16GB | 32GB | 64GB+ |
| GPU | 无 | RTX 2080+ | RTX 3090+ 或 A100 |
| 磁盘 | 200GB | 300GB | 500GB+ |
| 网络 | 10Mbps | 100Mbps | 1000Mbps |

### 软件要求

- **Python**: 3.9 或更高版本
- **操作系统**: Windows 10/11, macOS 12+, Ubuntu 20.04+
- **CUDA** (可选，用于GPU加速): 11.8 或更高版本
- **cuDNN** (可选，用于CUDA加速): 8.9 或更高版本

## 分步安装

### 第一步: 安装Python

#### Windows
1. 访问 [python.org](https://www.python.org/downloads/)
2. 下载 Python 3.10 或 3.11
3. 运行安装程序，**确保勾选 "Add Python to PATH"**
4. 验证安装:
   ```powershell
   python --version
   pip --version
   ```

#### macOS
```bash
# 使用Homebrew
brew install python3.11

# 验证
python3 --version
pip3 --version
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# 验证
python3.11 --version
pip3 --version
```

### 第二步: 克隆或复制项目

```bash
# 创建项目目录
mkdir -p ~/projects
cd ~/projects

# 复制项目文件（假设已从源获得）
# 或使用 git clone 如果已上传到git仓库
```

### 第三步: 创建虚拟环境

**强烈推荐使用虚拟环境隔离项目依赖**

#### Windows
```cmd
cd agent-model-system
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux
```bash
cd agent-model-system
python3.11 -m venv venv
source venv/bin/activate
```

验证激活:
```bash
# 命令行提示应该显示 (venv)
which python  # Linux/Mac
where python  # Windows
```

### 第四步: 升级pip（可选但推荐）

```bash
python -m pip install --upgrade pip setuptools wheel
```

### 第五步: 安装依赖包

```bash
# 安装基础依赖
pip install -r requirements.txt

# 如果需要GPU支持（CUDA 11.8）
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

验证安装:
```bash
python -c "import torch; print(torch.__version__)"
python -c "import transformers; print(transformers.__version__)"
```

### 第六步: 配置HuggingFace Token（推荐）

#### 方法1：环境变量

**Windows PowerShell:**
```powershell
$env:HUGGINGFACE_TOKEN = "your_actual_token"
```

**Windows CMD:**
```cmd
set HUGGINGFACE_TOKEN=your_actual_token
```

**Linux/macOS:**
```bash
export HUGGINGFACE_TOKEN="your_actual_token"
```

#### 方法2：.env 文件

复制 `.env.example` 为 `.env`:
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的token:
```ini
HUGGINGFACE_TOKEN=your_actual_token_here
```

#### 获取HuggingFace Token

1. 访问 https://huggingface.co/settings/tokens
2. 点击 "New token"
3. 创建新token（选择 "read" 权限即可）
4. 复制生成的token

### 第七步: 验证安装

```bash
# 检查所有模块能否正常导入
python -c "
from agents import InteractionAgent, ModelDownloadAgent, ModelFinetuneAgent
print('✅ 所有Agent模块导入成功')
"

# 尝试显示帮助信息
python main.py --help

# 检查系统配置
python main.py --list-agents
```

## GPU加速配置（可选）

### CUDA 安装

#### Windows
1. 访问 [NVIDIA CUDA Download](https://developer.nvidia.com/cuda-downloads)
2. 选择合适的版本（Windows, x86_64, 11.8 LTS）
3. 下载并运行安装程序
4. 安装到默认位置
5. 重启计算机

#### Linux (Ubuntu)
```bash
# 添加NVIDIA包库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 安装NVIDIA容器工具包
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# 重启Docker
sudo systemctl restart docker
```

### cuDNN 安装

1. 访问 [NVIDIA cuDNN Download](https://developer.nvidia.com/cudnn)
2. 注册NVIDIA开发者账号
3. 下载与CUDA版本对应的cuDNN
4. 解压并复制文件到CUDA安装目录

### 验证GPU

```python
import torch

print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
print(f"CUDA版本: {torch.version.cuda}")
print(f"GPU数量: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"GPU型号: {torch.cuda.get_device_name(0)}")
    print(f"GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.0f}GB")
```

## 常见安装问题

### 问题1: "ModuleNotFoundError: No module named 'torch'"

**原因**: PyTorch未安装或环境不正确

**解决方案**:
```bash
# 重新安装PyTorch
pip install torch --upgrade

# 或使用特定的CUDA版本
pip install torch==2.0.1 torchvision==0.15.2 torchaudio==0.15.2 --index-url https://download.pytorch.org/whl/cu118
```

### 问题2: "CUDA out of memory"

**原因**: GPU显存不足

**解决方案**:
1. 减小batch_size（从4改为2）
2. 使用更小的模型版本
3. 启用梯度检查点
4. 关闭其他GPU占用的应用

### 问题3: "HF 401 Unauthorized: Invalid token passed!"

**原因**: HuggingFace Token无效或未设置

**解决方案**:
```bash
# Windows PowerShell
$env:HUGGINGFACE_TOKEN = "new_token"

# Linux/Mac
export HUGGINGFACE_TOKEN="new_token"

# 重新设置后重启Python环境
```

### 问题4: "Connection timeout while downloading model"

**原因**: 网络连接问题或HF服务缓慢

**解决方案**:
```bash
# 设置代理（如果需要）
set HTTP_PROXY=http://proxy.example.com:8080
set HTTPS_PROXY=https://proxy.example.com:8080

# 或增加超时时间
export HF_DATASETS_CACHE=./models
```

### 问题5: "Permission denied" (Linux/Mac)

**原因**: 目录权限不足

**解决方案**:
```bash
# 给目录添加权限
chmod -R 755 agent-model-system
chmod -R u+w agent-model-system
```

## Docker安装（可选）

如果想使用Docker容器：

### 创建 Dockerfile

```dockerfile
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

WORKDIR /app

# 安装Python和依赖
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    git wget curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目
COPY . /app

# 创建虚拟环境并安装依赖
RUN python3.11 -m venv venv
RUN . venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

ENTRYPOINT ["venv/bin/python", "main.py"]
```

### 构建和运行

```bash
# 构建镜像
docker build -t agent-model-system .

# 运行容器
docker run --gpus all -it agent-model-system

# 带HuggingFace Token运行
docker run --gpus all -e HUGGINGFACE_TOKEN="your_token" -it agent-model-system
```

## 性能优化

### 1. 使用混合精度训练

在config.py中已启用（bf16=True）

### 2. 启用Flash Attention

```python
# 在微调配置中
"attn_implementation": "flash_attention_2"
```

### 3. 梯度检查点

```python
# 在微调配置中
"gradient_checkpointing": True
```

### 4. 分布式训练

对于多GPU系统，使用：
```bash
torchrun --nproc_per_node=4 main.py
```

## 卸载

如果需要完全卸载：

```bash
# 删除虚拟环境
rm -rf venv

# 删除缓存
rm -rf ~/.cache/huggingface/

# 删除项目（如果需要）
rm -rf agent-model-system
```

## 下一步

完成安装后：

1. 阅读 [QUICKSTART.md](QUICKSTART.md) 快速开始
2. 阅读 [README.md](README.md) 了解完整文档
3. 运行 `python main.py` 开始使用系统
4. 查看日志文件 `logs/agent_system.log` 了解详细信息

---

**需要帮助?** 检查日志文件或查看 [README.md](README.md) 中的故障排除部分。
