"""
交互Agent - 与用户交互，协调其他Agent的工作
"""
import json
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent


class InteractionAgent(BaseAgent):
    """
    交互Agent - 负责与用户交互和协调其他agents
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """初始化交互Agent"""
        super().__init__("InteractionAgent", log_file)
        self.supported_models = [
            "deepseek-1b",
            "deepseek-7b", 
            "deepseek-33b",
            "deepseek-chat",
            "deepseek-coder"
        ]
        self.model_selection = None
        self.finetune_params = {}
        
    def execute(self, download_agent=None, finetune_agent=None, **kwargs) -> Dict[str, Any]:
        """
        执行交互流程
        
        Args:
            download_agent: 模型下载agent实例
            finetune_agent: 模型微调agent实例
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        try:
            self.set_status("running")
            self.log_info("=" * 60)
            self.log_info("💼 欢迎使用AI模型Agent系统")
            self.log_info("=" * 60)
            
            # 1. 询问用户想要下载的模型
            self._display_welcome_message()
            model_info = self._ask_model_selection()
            
            if not model_info:
                self.log_error("用户未选择模型")
                return {"success": False, "message": "未选择模型"}
            
            self.model_selection = model_info
            self.log_info(f"✅ 用户选择模型: {model_info['model_name']}")
            
            # 2. 调用下载Agent下载模型
            if download_agent is None:
                self.log_error("下载Agent未提供")
                return {"success": False, "message": "下载Agent未提供"}
            
            self.log_info("📥 开始下载模型...")
            download_result = download_agent.execute(
                model_id=model_info['model_id'],
                model_name=model_info['model_name']
            )
            
            if not download_result.get("success"):
                self.log_error(f"模型下载失败: {download_result.get('message')}")
                return {"success": False, "message": "模型下载失败"}
            
            model_path = download_result.get("model_path")
            self.log_info(f"✅ 模型下载完成: {model_path}")
            
            # 3. 询问用户是否需要微调
            if self._ask_finetune():
                self.log_info("🔧 开始配置微调参数...")
                finetune_params = self._ask_finetune_params()
                
                if finetune_agent is None:
                    self.log_error("微调Agent未提供")
                    return {"success": False, "message": "微调Agent未提供"}
                
                self.log_info("⚙️ 开始微调模型...")
                finetune_result = finetune_agent.execute(
                    model_path=model_path,
                    model_id=model_info['model_id'],
                    finetune_params=finetune_params
                )
                
                if not finetune_result.get("success"):
                    self.log_error(f"模型微调失败: {finetune_result.get('message')}")
                    return {"success": False, "message": "模型微调失败"}
                
                self.log_info(f"✅ 模型微调完成: {finetune_result.get('model_path')}")
                
                # 4. 询问是否部署
                if self._ask_deploy():
                    self.log_info("🚀 开始部署模型...")
                    deploy_result = finetune_agent.deploy_model(
                        model_path=finetune_result.get('model_path'),
                        port=finetune_params.get('deploy_port', 8000)
                    )
                    
                    if deploy_result.get("success"):
                        self.log_info(f"✅ 模型部署成功!")
                        self.log_info(f"🌐 模型服务地址: {deploy_result.get('service_url')}")
                    else:
                        self.log_error(f"模型部署失败: {deploy_result.get('message')}")
            
            self.set_status("completed")
            self.log_info("=" * 60)
            self.log_info("✨ 所有任务完成！")
            self.log_info("=" * 60)
            
            return {
                "success": True,
                "message": "所有任务完成",
                "model_selection": self.model_selection,
                "download_path": model_path
            }
            
        except Exception as e:
            self.log_error(f"交互Agent执行失败: {str(e)}")
            self.set_status("failed")
            return {"success": False, "message": str(e)}
    
    def _display_welcome_message(self):
        """显示欢迎消息"""
        print("\n" + "=" * 60)
        print("🤖 AI模型Agent系统 - 三Agent协作系统")
        print("=" * 60)
        print("\n此系统包含三个Agent:")
        print("  1️⃣ InteractionAgent: 与用户交互，协调其他agents")
        print("  2️⃣ ModelDownloadAgent: 从HuggingFace下载Deepseek模型")
        print("  3️⃣ ModelFinetuneAgent: 使用LLamaFactory微调和部署模型")
        print("\n" + "=" * 60 + "\n")
    
    def _ask_model_selection(self) -> Optional[Dict[str, str]]:
        """询问用户选择要下载的模型"""
        print("\n📋 可用的Deepseek模型:")
        for idx, model in enumerate(self.supported_models, 1):
            print(f"  {idx}. {model}")
        
        while True:
            try:
                choice = input(f"\n请选择模型 (1-{len(self.supported_models)}): ").strip()
                choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(self.supported_models):
                    selected_model = self.supported_models[choice_idx]
                    model_id = f"deepseek-ai/{selected_model}"
                    return {
                        "model_name": selected_model,
                        "model_id": model_id
                    }
                else:
                    print("❌ 请输入有效的选项号")
            except ValueError:
                print("❌ 请输入数字")
    
    def _ask_finetune(self) -> bool:
        """询问用户是否需要微调模型"""
        while True:
            choice = input("\n❓ 是否需要微调模型? (y/n): ").strip().lower()
            if choice in ['y', 'yes', 'n', 'no']:
                return choice in ['y', 'yes']
            print("❌ 请输入 y 或 n")
    
    def _ask_finetune_params(self) -> Dict[str, Any]:
        """询问用户微调参数"""
        params = {}
        
        print("\n⚙️ 配置微调参数:")
        
        # 学习率
        while True:
            try:
                lr = float(input("  学习率 (默认: 1e-4): ") or "1e-4")
                params['learning_rate'] = lr
                break
            except ValueError:
                print("  ❌ 请输入有效的数字")
        
        # Batch size
        while True:
            try:
                batch_size = int(input("  Batch Size (默认: 4): ") or "4")
                params['batch_size'] = batch_size
                break
            except ValueError:
                print("  ❌ 请输入有效的数字")
        
        # Epochs
        while True:
            try:
                epochs = int(input("  训练轮数 (默认: 3): ") or "3")
                params['epochs'] = epochs
                break
            except ValueError:
                print("  ❌ 请输入有效的数字")
        
        # Deploy port
        while True:
            try:
                port = int(input("  部署端口 (默认: 8000): ") or "8000")
                params['deploy_port'] = port
                break
            except ValueError:
                print("  ❌ 请输入有效的数字")
        
        return params
    
    def _ask_deploy(self) -> bool:
        """询问用户是否部署模型"""
        while True:
            choice = input("\n❓ 是否将微调后的模型部署到本地? (y/n): ").strip().lower()
            if choice in ['y', 'yes', 'n', 'no']:
                return choice in ['y', 'yes']
            print("❌ 请输入 y 或 n")
