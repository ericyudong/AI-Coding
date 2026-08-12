"""
OCR引擎模块 - 支持多种OCR引擎
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
import os
import time
import base64
import io
import httpx
from dataclasses import dataclass


@dataclass
class OCRResult:
    """OCR识别结果"""
    text: str
    confidence: float
    details: List[Dict[str, Any]]
    processing_time: float
    engine_name: str


class BaseOCREngine(ABC):
    """OCR引擎基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "base"
    
    @abstractmethod
    def recognize(self, image: Image.Image) -> OCRResult:
        """识别图片中的文字"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        pass
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """图片预处理"""
        general_config = self.config.get("general", {})
        
        if not general_config.get("preprocess", True):
            return image
        
        # 转换为RGB（如果需要）
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 去噪
        if general_config.get("denoise", True):
            image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # 增强对比度
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # 二值化
        if general_config.get("threshold", True):
            image = image.convert('L')
            threshold = 128
            image = image.point(lambda x: 0 if x < threshold else 255, '1')
            image = image.convert('RGB')
        
        return image


class TesseractEngine(BaseOCREngine):
    """Tesseract OCR引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "tesseract"
        engine_config = config.get("tesseract", {})
        
        # 设置Tesseract路径
        tesseract_path = engine_config.get("path", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        self.lang = engine_config.get("lang", "chi_sim+eng")
        self.psm = engine_config.get("psm", 3)
        self.oem = engine_config.get("oem", 3)
    
    def recognize(self, image: Image.Image) -> OCRResult:
        """使用Tesseract识别"""
        start_time = time.time()
        
        # 预处理
        processed_image = self.preprocess_image(image)
        
        # 配置参数
        custom_config = f'--oem {self.oem} --psm {self.psm}'
        
        try:
            # 获取详细数据
            data = pytesseract.image_to_data(
                processed_image, 
                lang=self.lang, 
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            # 提取文本和置信度
            texts = []
            confidences = []
            details = []
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                
                if text and conf > 0:
                    texts.append(text)
                    confidences.append(conf)
                    details.append({
                        "text": text,
                        "confidence": conf,
                        "left": data['left'][i],
                        "top": data['top'][i],
                        "width": data['width'][i],
                        "height": data['height'][i],
                        "block_num": data['block_num'][i],
                        "line_num": data['line_num'][i]
                    })
            
            full_text = '\n'.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                details=details,
                processing_time=processing_time,
                engine_name=self.name
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text=f"识别错误: {str(e)}",
                confidence=0,
                details=[],
                processing_time=processing_time,
                engine_name=self.name
            )
    
    def is_available(self) -> bool:
        """检查Tesseract是否可用"""
        try:
            version = pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "paddleocr"
        self.ocr = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
            engine_config = self.config.get("paddleocr", {})
            
            # PaddleOCR 3.x 版本API变化，不再支持use_gpu参数
            self.ocr = PaddleOCR(
                lang=engine_config.get("lang", "ch"),
            )
        except ImportError:
            self.ocr = None
        except Exception as e:
            print(f"PaddleOCR初始化失败: {e}")
            self.ocr = None
    
    def recognize(self, image: Image.Image) -> OCRResult:
        """使用PaddleOCR识别"""
        start_time = time.time()
        
        if self.ocr is None:
            return OCRResult(
                text="PaddleOCR未安装，请运行: pip install paddleocr paddlepaddle",
                confidence=0,
                details=[],
                processing_time=0,
                engine_name=self.name
            )
        
        try:
            import numpy as np
            img_array = np.array(image)
            
            result = self.ocr.ocr(img_array, cls=True)
            
            texts = []
            details = []
            confidences = []
            
            if result and result[0]:
                for line in result[0]:
                    box = line[0]
                    text = line[1][0]
                    conf = line[1][1]
                    
                    texts.append(text)
                    confidences.append(conf)
                    
                    # 计算边界框
                    x_coords = [p[0] for p in box]
                    y_coords = [p[1] for p in box]
                    
                    details.append({
                        "text": text,
                        "confidence": conf,
                        "box": box,
                        "left": min(x_coords),
                        "top": min(y_coords),
                        "width": max(x_coords) - min(x_coords),
                        "height": max(y_coords) - min(y_coords)
                    })
            
            full_text = '\n'.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                details=details,
                processing_time=processing_time,
                engine_name=self.name
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text=f"识别错误: {str(e)}",
                confidence=0,
                details=[],
                processing_time=processing_time,
                engine_name=self.name
            )
    
    def is_available(self) -> bool:
        """检查PaddleOCR是否可用"""
        return self.ocr is not None


class EasyOCREngine(BaseOCREngine):
    """EasyOCR引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "easyocr"
        self.reader = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化EasyOCR"""
        try:
            import easyocr
            engine_config = self.config.get("easyocr", {})
            
            self.reader = easyocr.Reader(
                lang_list=engine_config.get("lang_list", ["ch_sim", "en"]),
                gpu=engine_config.get("gpu", False)
            )
        except ImportError:
            self.reader = None
    
    def recognize(self, image: Image.Image) -> OCRResult:
        """使用EasyOCR识别"""
        start_time = time.time()
        
        if self.reader is None:
            return OCRResult(
                text="EasyOCR未安装，请运行: pip install easyocr",
                confidence=0,
                details=[],
                processing_time=0,
                engine_name=self.name
            )
        
        try:
            import numpy as np
            img_array = np.array(image)
            
            results = self.reader.readtext(img_array)
            
            texts = []
            details = []
            confidences = []
            
            for (box, text, conf) in results:
                texts.append(text)
                confidences.append(conf)
                
                # 计算边界框
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
                
                details.append({
                    "text": text,
                    "confidence": conf,
                    "box": box,
                    "left": min(x_coords),
                    "top": min(y_coords),
                    "width": max(x_coords) - min(x_coords),
                    "height": max(y_coords) - min(y_coords)
                })
            
            full_text = '\n'.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                details=details,
                processing_time=processing_time,
                engine_name=self.name
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return OCRResult(
                text=f"识别错误: {str(e)}",
                confidence=0,
                details=[],
                processing_time=processing_time,
                engine_name=self.name
            )
    
    def is_available(self) -> bool:
        """检查EasyOCR是否可用"""
        return self.reader is not None


class OvisOCREngine(BaseOCREngine):
    """OvisOCR引擎 - 基于OpenAI兼容API的视觉大模型OCR"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "ovisocr"
        self.api_url = None
        self.api_key = None
        self.model_id = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化OvisOCR"""
        try:
            engine_config = self.config.get("ovisocr", {})
            self.api_url = engine_config.get("api_url", "https://maas.ehuidata.com/openai/v1")
            self.api_key = engine_config.get("api_key", "")
            self.model_id = engine_config.get("model_id", "OvisOCR")
        except Exception as e:
            print(f"OvisOCR初始化失败: {e}")
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """将图片转换为base64"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    def recognize(self, image: Image.Image) -> OCRResult:
        """使用OvisOCR识别"""
        start_time = time.time()
        
        if not self.api_key:
            return OCRResult(
                text="OvisOCR未配置API Key，请在配置页面设置",
                confidence=0,
                details=[],
                processing_time=0,
                engine_name=self.name
            )
        
        try:
            # 将图片转换为base64
            img_base64 = self._image_to_base64(image)
            
            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "请识别图片中的所有文字内容，只返回识别到的文字，不要添加任何解释。"
                            }
                        ]
                    }
                ],
                "max_tokens": 4096
            }
            
            # 发送请求
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_msg = response.text
                    return OCRResult(
                        text=f"API请求失败: {response.status_code} - {error_msg}",
                        confidence=0,
                        details=[],
                        processing_time=time.time() - start_time,
                        engine_name=self.name
                    )
                
                result = response.json()
                
                # 提取识别文本（防御 None 值）
                text = ""
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {}) or {}
                    text = message.get("content", "") or ""
                
                processing_time = time.time() - start_time
                
                return OCRResult(
                    text=text.strip() if isinstance(text, str) else "",
                    confidence=0.95,  # API模型默认较高置信度
                    details=[],
                    processing_time=processing_time,
                    engine_name=self.name
                )
                
        except httpx.TimeoutException:
            return OCRResult(
                text="OvisOCR请求超时，请稍后重试",
                confidence=0,
                details=[],
                processing_time=time.time() - start_time,
                engine_name=self.name
            )
        except Exception as e:
            return OCRResult(
                text=f"识别错误: {str(e)}",
                confidence=0,
                details=[],
                processing_time=time.time() - start_time,
                engine_name=self.name
            )
    
    def is_available(self) -> bool:
        """检查OvisOCR是否可用"""
        return bool(self.api_key and self.api_url)


class OCREngineManager:
    """OCR引擎管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.engines: Dict[str, BaseOCREngine] = {}
        self._init_engines()
    
    def _init_engines(self):
        """初始化所有引擎"""
        self.engines["tesseract"] = TesseractEngine(self.config)
        self.engines["paddleocr"] = PaddleOCREngine(self.config)
        self.engines["easyocr"] = EasyOCREngine(self.config)
        self.engines["ovisocr"] = OvisOCREngine(self.config)
    
    def get_engine(self, name: Optional[str] = None) -> BaseOCREngine:
        """获取指定引擎"""
        engine_name = name if name is not None else self.config.get("current_engine", "tesseract")
        
        if engine_name not in self.engines:
            raise ValueError(f"未知的OCR引擎: {engine_name}")
        
        return self.engines[engine_name]
    
    def get_available_engines(self) -> List[str]:
        """获取可用的引擎列表"""
        available = []
        for name, engine in self.engines.items():
            if engine.is_available():
                available.append(name)
        return available
    
    def get_engine_status(self) -> Dict[str, bool]:
        """获取所有引擎状态"""
        return {name: engine.is_available() for name, engine in self.engines.items()}
    
    def recognize(self, image: Image.Image, engine_name: Optional[str] = None) -> OCRResult:
        """使用指定引擎识别"""
        engine = self.get_engine(engine_name)
        return engine.recognize(image)
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置并重新初始化引擎"""
        self._deep_update(self.config, new_config)
        self._init_engines()
    
    def _deep_update(self, d: dict, u: dict):
        """深度更新字典"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v