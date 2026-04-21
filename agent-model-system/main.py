#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent 模型管理系统 - 主程序

三Agent协作系统：
1. InteractionAgent: 与用户交互，协调其他agents
2. ModelDownloadAgent: 从HuggingFace下载Deepseek模型
3. ModelFinetuneAgent: 使用LLamaFactory微调和部署模型
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from agents import InteractionAgent, ModelDownloadAgent, ModelFinetuneAgent
from config import (
    SYSTEM_NAME, SYSTEM_VERSION, SYSTEM_DESCRIPTION,
    AGENTS_CONFIG, LOG_LEVEL, LOG_FILE
)


def setup_logging():
    """设置全局日志记录"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )


def print_banner():
    """打印系统banner"""
    print("\n" + "="*70)
    print(f"🤖 {SYSTEM_NAME}")
    print(f"版本: {SYSTEM_VERSION}")
    print(f"描述: {SYSTEM_DESCRIPTION}")
    print("="*70 + "\n")


def main():
    """
    主函数 - 协调三个Agent的工作流程
    """
    try:
        # 设置日志
        setup_logging()
        logger = logging.getLogger("MainProgram")
        
        # 打印欢迎信息
        print_banner()
        
        logger.info(f"启动 {SYSTEM_NAME}")
        
        # 检查Agent配置
        logger.info("初始化Agent...")
        
        # 1. 创建ModelDownloadAgent (下载Agent)
        download_config = AGENTS_CONFIG.get("ModelDownloadAgent", {})
        if download_config.get("enabled"):
            download_agent = ModelDownloadAgent(
                model_dir=download_config.get("model_dir"),
                log_file=download_config.get("log_file")
            )
            logger.info("✅ ModelDownloadAgent已初始化")
        else:
            logger.error("ModelDownloadAgent未启用")
            return
        
        # 2. 创建ModelFinetuneAgent (微调Agent)
        finetune_config = AGENTS_CONFIG.get("ModelFinetuneAgent", {})
        if finetune_config.get("enabled"):
            finetune_agent = ModelFinetuneAgent(
                output_dir=finetune_config.get("output_dir"),
                log_file=finetune_config.get("log_file")
            )
            logger.info("✅ ModelFinetuneAgent已初始化")
        else:
            logger.error("ModelFinetuneAgent未启用")
            return
        
        # 3. 创建InteractionAgent (交互Agent)
        interaction_config = AGENTS_CONFIG.get("InteractionAgent", {})
        if interaction_config.get("enabled"):
            interaction_agent = InteractionAgent(
                log_file=interaction_config.get("log_file")
            )
            logger.info("✅ InteractionAgent已初始化")
        else:
            logger.error("InteractionAgent未启用")
            return
        
        logger.info("所有Agent已成功初始化")
        
        # 4. 执行主工作流程
        logger.info("开始执行Agent工作流程...")
        result = interaction_agent.execute(
            download_agent=download_agent,
            finetune_agent=finetune_agent
        )
        
        # 5. 输出最终结果
        print("\n" + "="*70)
        print("📊 执行结果汇总")
        print("="*70)
        print(f"成功: {result.get('success')}")
        print(f"消息: {result.get('message')}")
        if result.get('model_selection'):
            print(f"选择模型: {result['model_selection'].get('model_name')}")
        if result.get('download_path'):
            print(f"模型路径: {result['download_path']}")
        print("="*70 + "\n")
        
        if result.get('success'):
            logger.info("✨ 系统执行成功！")
        else:
            logger.error("❌ 系统执行失败")
        
        return 0 if result.get('success') else 1
        
    except Exception as e:
        logger.error(f"系统执行错误: {str(e)}", exc_info=True)
        print(f"\n❌ 错误: {str(e)}")
        return 1


def print_help():
    """打印帮助信息"""
    help_text = """
使用方法:
    python main.py [选项]

选项:
    --help, -h          显示此帮助信息
    --check-models      检查已下载的模型
    --list-agents       列出所有Agent
    --version           显示系统版本

示例:
    python main.py                  # 启动完整的Agent工作流程
    python main.py --check-models   # 检查已下载的模型
    python main.py --list-agents    # 列出所有Agent
    python main.py --version        # 显示系统版本

系统说明:
    本系统包含三个Agent:
    
    1. InteractionAgent (交互Agent)
       - 负责与用户交互
       - 询问用户想要下载的模型
       - 协调其他两个Agent的工作
    
    2. ModelDownloadAgent (下载Agent)
       - 从HuggingFace下载Deepseek最新模型
       - 支持断点续传
       - 提供模型列表和管理功能
    
    3. ModelFinetuneAgent (微调Agent)
       - 使用LLamaFactory对下载的模型进行微调
       - 生成样本训练数据
       - 支持模型部署到本地服务

更多信息，请查看 README.md
"""
    print(help_text)


def check_models():
    """检查已下载的模型"""
    from config import AGENTS_CONFIG
    
    download_config = AGENTS_CONFIG.get("ModelDownloadAgent", {})
    download_agent = ModelDownloadAgent(
        model_dir=download_config.get("model_dir"),
        log_file=download_config.get("log_file")
    )
    
    models = download_agent.list_downloaded_models()
    
    print("\n" + "="*70)
    print("📦 已下载的模型列表")
    print("="*70)
    
    if not models:
        print("未找到已下载的模型")
    else:
        for idx, model in enumerate(models, 1):
            print(f"\n{idx}. {model['name']}")
            print(f"   路径: {model['path']}")
            print(f"   大小: {model['size']}")
    
    print("\n" + "="*70 + "\n")


def list_agents():
    """列出所有Agent"""
    print("\n" + "="*70)
    print("🤖 可用的Agent列表")
    print("="*70)
    print("""
1. InteractionAgent (交互Agent)
   - 类名: InteractionAgent
   - 文件: agents/interaction_agent.py
   - 功能: 与用户交互，协调其他agents
   
2. ModelDownloadAgent (下载Agent)
   - 类名: ModelDownloadAgent
   - 文件: agents/download_agent.py
   - 功能: 从HuggingFace下载Deepseek模型
   
3. ModelFinetuneAgent (微调Agent)
   - 类名: ModelFinetuneAgent
   - 文件: agents/finetune_agent.py
   - 功能: 使用LLamaFactory微调和部署模型
""")
    print("="*70 + "\n")


if __name__ == "__main__":
    # 处理命令行参数
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h']:
            print_help()
            sys.exit(0)
        elif arg == '--check-models':
            check_models()
            sys.exit(0)
        elif arg == '--list-agents':
            list_agents()
            sys.exit(0)
        elif arg == '--version':
            print(f"{SYSTEM_NAME} v{SYSTEM_VERSION}")
            sys.exit(0)
        else:
            print(f"未知的选项: {arg}")
            print_help()
            sys.exit(1)
    
    # 运行主程序
    exit_code = main()
    sys.exit(exit_code)
