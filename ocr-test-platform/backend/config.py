"""
OCR平台配置模块
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
import json
import os


class OCRConfig(BaseSettings):
    """OCR配置"""
    # 当前使用的OCR引擎
    current_engine: str = "tesseract"
    
    # Tesseract配置
    tesseract_path: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    tesseract_lang: str = "chi_sim+eng"
    
    # PaddleOCR配置
    paddle_use_gpu: bool = False
    paddle_lang: str = "ch"
    
    # 通用配置
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"]
    
    # 上传目录
    upload_dir: str = "./uploads"
    
    class Config:
        env_file = ".env"


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "ocr_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "current_engine": "tesseract",
            "tesseract": {
                "path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                "lang": "chi_sim+eng",
                "psm": 3,
                "oem": 3
            },
            "paddleocr": {
                "use_gpu": False,
                "lang": "ch",
                "use_angle_cls": True
            },
            "easyocr": {
                "lang_list": ["ch_sim", "en"],
                "gpu": False
            },
            "ovisocr": {
                "model_id": "OvisOCR",
                "api_url": "https://maas.ehuidata.com/openai/v1",
                "api_key": "3c232be97e25f5d0fd3166002b4b41c331ae217_2049043995380019201"
            },
            "general": {
                "max_file_size": 52428800,
                "preprocess": True,
                "denoise": True,
                "threshold": True
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    # 合并配置
                    self._deep_update(default_config, saved_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return default_config
    
    def _deep_update(self, d: dict, u: dict):
        """深度更新字典"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
    
    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self.config
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        self._deep_update(self.config, new_config)
        return self.save_config()
    
    def get_engine_config(self, engine_name: str) -> Dict[str, Any]:
        """获取指定引擎配置"""
        return self.config.get(engine_name, {})
    
    def set_current_engine(self, engine_name: str) -> bool:
        """设置当前引擎"""
        self.config["current_engine"] = engine_name
        return self.save_config()


# 全局配置实例
config_manager = ConfigManager()