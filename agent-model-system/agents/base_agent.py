"""
基础Agent类 - 所有Agent的基类
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime


class BaseAgent(ABC):
    """所有Agent的基类"""
    
    def __init__(self, agent_name: str, log_file: Optional[str] = None):
        """
        初始化基础Agent
        
        Args:
            agent_name: Agent名称
            log_file: 日志文件路径
        """
        self.agent_name = agent_name
        self.logger = self._setup_logger(agent_name, log_file)
        self.status = "initialized"
        self.created_time = datetime.now()
        
    def _setup_logger(self, name: str, log_file: Optional[str]) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行Agent的主要任务
        
        Args:
            **kwargs: 执行参数
            
        Returns:
            包含执行结果的字典
        """
        pass
    
    def log_info(self, message: str):
        """记录信息"""
        self.logger.info(message)
    
    def log_error(self, message: str):
        """记录错误"""
        self.logger.error(message)
    
    def log_debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
    
    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "created_time": self.created_time.isoformat()
        }
    
    def set_status(self, status: str):
        """设置Agent状态"""
        self.status = status
        self.log_info(f"Agent状态更新: {status}")
