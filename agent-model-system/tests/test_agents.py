"""
Agent系统的测试框架
使用 pytest 进行单元测试

运行测试: pytest tests/
运行特定测试: pytest tests/test_agents.py
"""

import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from agents import BaseAgent, InteractionAgent, ModelDownloadAgent, ModelFinetuneAgent


class TestBaseAgent:
    """测试BaseAgent基类"""
    
    def test_agent_creation(self):
        """测试Agent创建"""
        # BaseAgent是抽象类，不能直接实例化
        # 但我们可以测试其子类
        agent = ModelDownloadAgent()
        assert agent.agent_name == "ModelDownloadAgent"
        assert agent.status == "initialized"
    
    def test_agent_logging(self):
        """测试Agent日志记录"""
        agent = ModelDownloadAgent()
        # 测试日志方法（不应该抛出异常）
        agent.log_info("测试信息")
        agent.log_error("测试错误")
        agent.log_debug("测试调试")
    
    def test_agent_status(self):
        """测试Agent状态管理"""
        agent = ModelDownloadAgent()
        assert agent.status == "initialized"
        
        agent.set_status("running")
        assert agent.status == "running"
        
        agent.set_status("completed")
        assert agent.status == "completed"
    
    def test_agent_get_status(self):
        """测试获取Agent状态"""
        agent = ModelDownloadAgent()
        status = agent.get_status()
        
        assert "agent_name" in status
        assert "status" in status
        assert "created_time" in status
        assert status["agent_name"] == "ModelDownloadAgent"
        assert status["status"] == "initialized"


class TestModelDownloadAgent:
    """测试ModelDownloadAgent"""
    
    def test_agent_initialization(self):
        """测试下载Agent初始化"""
        agent = ModelDownloadAgent(model_dir="./test_models")
        assert agent.agent_name == "ModelDownloadAgent"
        assert agent.model_dir == "./test_models"
        assert agent.status == "initialized"
    
    def test_list_empty_models(self):
        """测试列出空模型列表"""
        agent = ModelDownloadAgent(model_dir="./nonexistent_dir")
        models = agent.list_downloaded_models()
        assert isinstance(models, list)
    
    def test_agent_execution(self):
        """测试下载Agent执行（不实际下载）"""
        agent = ModelDownloadAgent()
        # 这会尝试下载，可能需要网络
        # 在实际测试中，可以使用mock来模拟
        # result = agent.execute(model_id="test", model_name="test")
        # assert "success" in result or "message" in result


class TestInteractionAgent:
    """测试InteractionAgent"""
    
    def test_agent_initialization(self):
        """测试交互Agent初始化"""
        agent = InteractionAgent()
        assert agent.agent_name == "InteractionAgent"
        assert agent.status == "initialized"
        assert len(agent.supported_models) > 0
    
    def test_supported_models(self):
        """测试支持的模型列表"""
        agent = InteractionAgent()
        assert "deepseek-7b" in agent.supported_models
        assert "deepseek-chat" in agent.supported_models


class TestModelFinetuneAgent:
    """测试ModelFinetuneAgent"""
    
    def test_agent_initialization(self):
        """测试微调Agent初始化"""
        agent = ModelFinetuneAgent(output_dir="./test_output")
        assert agent.agent_name == "ModelFinetuneAgent"
        assert agent.status == "initialized"
        assert agent.output_dir == "./test_output"
    
    def test_create_config(self):
        """测试创建微调配置"""
        agent = ModelFinetuneAgent()
        config = agent._create_finetune_config(
            model_path="./test_model",
            model_id="deepseek-ai/deepseek-7b",
            finetune_params={
                "learning_rate": 1e-4,
                "batch_size": 4,
                "epochs": 3
            }
        )
        
        assert "model_name_or_path" in config
        assert "learning_rate" in config
        assert config["learning_rate"] == 1e-4
        assert config["per_device_train_batch_size"] == 4
        assert config["num_train_epochs"] == 3


class TestSystemIntegration:
    """系统集成测试"""
    
    def test_all_agents_instantiation(self):
        """测试所有Agent能否实例化"""
        agents = {
            "InteractionAgent": InteractionAgent(),
            "ModelDownloadAgent": ModelDownloadAgent(),
            "ModelFinetuneAgent": ModelFinetuneAgent()
        }
        
        for name, agent in agents.items():
            assert agent is not None
            assert agent.agent_name == name
            assert agent.status == "initialized"
    
    def test_agents_communication(self):
        """测试Agent之间能否正常通信结构"""
        # 创建所有Agent
        interaction = InteractionAgent()
        download = ModelDownloadAgent()
        finetune = ModelFinetuneAgent()
        
        # 检查Agent能否接受彼此的实例
        # 这只是验证接口兼容性
        assert callable(interaction.execute)
        assert callable(download.execute)
        assert callable(finetune.execute)


@pytest.fixture
def setup_test_env():
    """设置测试环境"""
    # 创建测试目录
    Path("./test_output").mkdir(exist_ok=True)
    Path("./test_models").mkdir(exist_ok=True)
    
    yield
    
    # 清理测试目录
    import shutil
    if Path("./test_output").exists():
        shutil.rmtree("./test_output")
    if Path("./test_models").exists():
        shutil.rmtree("./test_models")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
