"""
系统配置文件
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 模型相关配置
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
FINETUNED_MODELS_DIR = os.path.join(PROJECT_ROOT, "finetuned_models")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# HuggingFace API配置
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", None)
HUGGINGFACE_CACHE_DIR = os.getenv("HUGGINGFACE_HOME", None)

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(LOGS_DIR, "agent_system.log")

# 支持的Deepseek模型列表
DEEPSEEK_MODELS = {
    "deepseek-1b": "deepseek-ai/deepseek-1b",
    "deepseek-7b": "deepseek-ai/deepseek-7b",
    "deepseek-33b": "deepseek-ai/deepseek-33b",
    "deepseek-chat": "deepseek-ai/deepseek-chat",
    "deepseek-coder": "deepseek-ai/deepseek-coder"
}

# 微调默认参数
DEFAULT_FINETUNE_PARAMS = {
    "learning_rate": 1e-4,
    "batch_size": 4,
    "epochs": 3,
    "max_seq_length": 2048,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "gradient_accumulation_steps": 4
}

# 部署配置
DEFAULT_DEPLOY_PORT = 8000

# 创建必要的目录
for directory in [MODELS_DIR, FINETUNED_MODELS_DIR, LOGS_DIR]:
    Path(directory).mkdir(parents=True, exist_ok=True)

# 系统信息
SYSTEM_NAME = "AI Agent Model Management System"
SYSTEM_VERSION = "1.0.0"
SYSTEM_DESCRIPTION = "三Agent协作系统：交互Agent、下载Agent、微调Agent"

# Agent配置
AGENTS_CONFIG = {
    "InteractionAgent": {
        "enabled": True,
        "log_file": os.path.join(LOGS_DIR, "interaction_agent.log")
    },
    "ModelDownloadAgent": {
        "enabled": True,
        "model_dir": MODELS_DIR,
        "log_file": os.path.join(LOGS_DIR, "download_agent.log")
    },
    "ModelFinetuneAgent": {
        "enabled": True,
        "output_dir": FINETUNED_MODELS_DIR,
        "log_file": os.path.join(LOGS_DIR, "finetune_agent.log")
    }
}
