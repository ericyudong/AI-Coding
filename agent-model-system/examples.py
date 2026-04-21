"""
Agent系统使用示例脚本
展示如何直接使用Agents而不是通过命令行交互

可以直接运行: python examples.py
"""

import sys
import os

# 添加项目根目录到Python路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from agents import ModelDownloadAgent, ModelFinetuneAgent, InteractionAgent
from config import AGENTS_CONFIG


def example_1_download_only():
    """
    示例1: 仅下载模型，不进行微调
    """
    print("\n" + "="*70)
    print("示例 1: 仅下载模型")
    print("="*70 + "\n")
    
    # 创建下载Agent
    download_agent = ModelDownloadAgent(
        model_dir=AGENTS_CONFIG["ModelDownloadAgent"]["model_dir"]
    )
    
    # 下载deepseek-7b模型
    result = download_agent.execute(
        model_id="deepseek-ai/deepseek-7b",
        model_name="deepseek-7b"
    )
    
    if result["success"]:
        print(f"\n✅ 模型下载成功!")
        print(f"📍 模型路径: {result['model_path']}")
    else:
        print(f"\n❌ 模型下载失败: {result['message']}")


def example_2_download_and_list():
    """
    示例2: 下载模型后列出所有已下载的模型
    """
    print("\n" + "="*70)
    print("示例 2: 下载并列出所有模型")
    print("="*70 + "\n")
    
    # 创建下载Agent
    download_agent = ModelDownloadAgent(
        model_dir=AGENTS_CONFIG["ModelDownloadAgent"]["model_dir"]
    )
    
    # 下载模型
    print("📥 下载deepseek-chat模型...")
    result = download_agent.execute(
        model_id="deepseek-ai/deepseek-chat",
        model_name="deepseek-chat"
    )
    
    if result["success"]:
        print("✅ 下载完成")
        
        # 列出所有已下载的模型
        print("\n📦 所有已下载的模型:")
        models = download_agent.list_downloaded_models()
        for idx, model in enumerate(models, 1):
            print(f"\n{idx}. {model['name']}")
            print(f"   路径: {model['path']}")
            print(f"   大小: {model['size']}")
    else:
        print(f"❌ 下载失败: {result['message']}")


def example_3_finetune():
    """
    示例3: 微调已下载的模型
    
    注意: 请确保模型已经下载
    """
    print("\n" + "="*70)
    print("示例 3: 微调模型")
    print("="*70 + "\n")
    
    # 假设模型已下载到这个路径
    model_path = "./models/deepseek-7b"
    
    if not os.path.exists(model_path):
        print(f"❌ 模型不存在: {model_path}")
        print("请先运行 example_1 下载模型")
        return
    
    # 创建微调Agent
    finetune_agent = ModelFinetuneAgent(
        output_dir=AGENTS_CONFIG["ModelFinetuneAgent"]["output_dir"]
    )
    
    # 配置微调参数
    finetune_params = {
        "learning_rate": 5e-5,
        "batch_size": 4,
        "epochs": 2,
        "deploy_port": 8000
    }
    
    print("🔧 开始微调模型...")
    result = finetune_agent.execute(
        model_path=model_path,
        model_id="deepseek-ai/deepseek-7b",
        finetune_params=finetune_params
    )
    
    if result["success"]:
        print(f"\n✅ 模型微调完成!")
        print(f"📍 微调模型路径: {result['model_path']}")
    else:
        print(f"\n❌ 模型微调失败: {result['message']}")


def example_4_deploy():
    """
    示例4: 部署微调后的模型
    
    注意: 请确保模型已经微调
    """
    print("\n" + "="*70)
    print("示例 4: 部署微调后的模型")
    print("="*70 + "\n")
    
    # 假设微调模型已生成
    model_path = "./finetuned_models/final_model"
    
    if not os.path.exists(model_path):
        print(f"❌ 微调模型不存在: {model_path}")
        print("请先运行 example_3 微调模型")
        return
    
    # 创建微调Agent
    finetune_agent = ModelFinetuneAgent(
        output_dir=AGENTS_CONFIG["ModelFinetuneAgent"]["output_dir"]
    )
    
    # 部署模型
    print("🚀 部署模型...")
    result = finetune_agent.deploy_model(
        model_path=model_path,
        port=8000
    )
    
    if result["success"]:
        print(f"\n✅ 模型部署成功!")
        print(f"🌐 服务地址: {result['service_url']}")
        print(f"📄 部署脚本: {result['deploy_script']}")
        print(f"\n运行以下命令启动服务:")
        print(f"python {result['deploy_script']}")
    else:
        print(f"\n❌ 模型部署失败: {result['message']}")


def example_5_full_workflow():
    """
    示例5: 完整工作流程（下载 -> 微调 -> 部署）
    
    这是一个自动化的完整工作流程示例
    """
    print("\n" + "="*70)
    print("示例 5: 完整工作流程（自动化）")
    print("="*70 + "\n")
    
    # 创建所有Agents
    download_agent = ModelDownloadAgent(
        model_dir=AGENTS_CONFIG["ModelDownloadAgent"]["model_dir"]
    )
    finetune_agent = ModelFinetuneAgent(
        output_dir=AGENTS_CONFIG["ModelFinetuneAgent"]["output_dir"]
    )
    interaction_agent = InteractionAgent(
        log_file=AGENTS_CONFIG["InteractionAgent"]["log_file"]
    )
    
    # 执行完整工作流程
    result = interaction_agent.execute(
        download_agent=download_agent,
        finetune_agent=finetune_agent
    )
    
    print(f"\n\n📊 工作流程结果:")
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")


def print_menu():
    """打印选择菜单"""
    print("\n" + "="*70)
    print("🤖 AI Agent 系统 - 使用示例")
    print("="*70)
    print("\n请选择要运行的示例:\n")
    print("  1. 仅下载模型")
    print("  2. 下载并列出所有模型")
    print("  3. 微调模型")
    print("  4. 部署微调后的模型")
    print("  5. 完整工作流程（自动化）")
    print("  0. 退出")
    print("\n" + "="*70)


if __name__ == "__main__":
    # 提供菜单选择或直接运行特定示例
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        # 交互式菜单
        while True:
            print_menu()
            choice = input("\n请输入选项 (0-5): ").strip()
            
            if choice == "1":
                example_1_download_only()
            elif choice == "2":
                example_2_download_and_list()
            elif choice == "3":
                example_3_finetune()
            elif choice == "4":
                example_4_deploy()
            elif choice == "5":
                example_5_full_workflow()
            elif choice == "0":
                print("\n👋 再见!")
                break
            else:
                print("\n❌ 无效选项，请重试")
            
            input("\n按Enter键继续...")
