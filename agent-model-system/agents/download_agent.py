"""
模型下载Agent - 负责从HuggingFace下载Deepseek模型
"""
import os
from typing import Any, Dict, Optional
from pathlib import Path
from agents.base_agent import BaseAgent


class ModelDownloadAgent(BaseAgent):
    """
    模型下载Agent - 从HuggingFace下载Deepseek模型
    """
    
    def __init__(self, model_dir: str = "./models", log_file: Optional[str] = None):
        """
        初始化模型下载Agent
        
        Args:
            model_dir: 模型存储目录
            log_file: 日志文件路径
        """
        super().__init__("ModelDownloadAgent", log_file)
        self.model_dir = model_dir
        self.huggingface_token = os.getenv("HUGGINGFACE_TOKEN", None)
        
        # 创建模型目录
        Path(model_dir).mkdir(parents=True, exist_ok=True)
    
    def execute(self, model_id: str, model_name: str, **kwargs) -> Dict[str, Any]:
        """
        下载指定的Deepseek模型
        
        Args:
            model_id: HuggingFace模型ID (e.g., 'deepseek-ai/deepseek-7b')
            model_name: 模型名称
            **kwargs: 其他参数
            
        Returns:
            包含下载结果的字典
        """
        try:
            self.set_status("downloading")
            self.log_info(f"开始下载模型: {model_name} ({model_id})")
            
            # 模型本地存储路径
            model_path = os.path.join(self.model_dir, model_name.replace("/", "_"))
            
            # 检查模型是否已存在
            if os.path.exists(model_path):
                self.log_info(f"模型已存在于: {model_path}")
                return {
                    "success": True,
                    "message": "模型已存在",
                    "model_path": model_path,
                    "model_id": model_id,
                    "model_name": model_name
                }
            
            # 使用transformers库下载模型
            self._download_from_huggingface(model_id, model_path)
            
            self.set_status("completed")
            self.log_info(f"✅ 模型下载完成: {model_path}")
            
            return {
                "success": True,
                "message": "模型下载成功",
                "model_path": model_path,
                "model_id": model_id,
                "model_name": model_name
            }
            
        except Exception as e:
            self.log_error(f"模型下载失败: {str(e)}")
            self.set_status("failed")
            return {
                "success": False,
                "message": f"模型下载失败: {str(e)}"
            }
    
    def _download_from_huggingface(self, model_id: str, model_path: str):
        """
        从HuggingFace下载模型
        
        Args:
            model_id: HuggingFace模型ID
            model_path: 本地存储路径
        """
        try:
            from huggingface_hub import snapshot_download
            
            self.log_info(f"从HuggingFace下载模型...")
            self.log_debug(f"模型ID: {model_id}")
            self.log_debug(f"存储路径: {model_path}")
            
            # 下载模型
            downloaded_path = snapshot_download(
                repo_id=model_id,
                local_dir=model_path,
                resume_download=True,
                token=self.huggingface_token,
                local_dir_use_symlinks=False
            )
            
            self.log_info(f"模型文件下载到: {downloaded_path}")
            
        except ImportError:
            self.log_error("huggingface_hub库未安装，尝试使用transformers库...")
            self._download_using_transformers(model_id, model_path)
    
    def _download_using_transformers(self, model_id: str, model_path: str):
        """
        使用transformers库下载模型（备选方案）
        
        Args:
            model_id: HuggingFace模型ID
            model_path: 本地存储路径
        """
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            self.log_info(f"使用transformers库下载模型...")
            
            # 创建目录
            Path(model_path).mkdir(parents=True, exist_ok=True)
            
            # 下载tokenizer
            self.log_info("下载Tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True,
                token=self.huggingface_token
            )
            tokenizer.save_pretrained(model_path)
            self.log_info("✅ Tokenizer保存完成")
            
            # 下载模型（可选，因为模型文件通常很大）
            self.log_info("下载模型权重（这可能需要一些时间）...")
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                trust_remote_code=True,
                device_map="cpu",
                token=self.huggingface_token
            )
            model.save_pretrained(model_path)
            self.log_info("✅ 模型权重保存完成")
            
        except Exception as e:
            self.log_error(f"模型下载失败: {str(e)}")
            raise
    
    def list_downloaded_models(self) -> list:
        """列出已下载的模型"""
        if not os.path.exists(self.model_dir):
            return []
        
        models = []
        for item in os.listdir(self.model_dir):
            model_path = os.path.join(self.model_dir, item)
            if os.path.isdir(model_path):
                models.append({
                    "name": item,
                    "path": model_path,
                    "size": self._get_dir_size(model_path)
                })
        
        return models
    
    def _get_dir_size(self, path: str) -> str:
        """获取目录大小"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        
        # 转换为可读的大小
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_size < 1024:
                return f"{total_size:.2f}{unit}"
            total_size /= 1024
        
        return f"{total_size:.2f}TB"
