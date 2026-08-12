# Agent Harness Framework

一个支持Agent运行时管理、内存管理和自进化功能的工程框架。

## 核心特性

- **Agent运行时管理**: 完整的Agent生命周期管理，包括初始化、执行、暂停、恢复和终止
- **内存管理系统**: 支持短期记忆、长期记忆、工作记忆的多层次内存架构
- **运行时数据收集**: 自动收集Agent运行时的行为数据、性能指标和交互记录
- **自进化引擎**: 基于收集的运行时数据，自动优化Agent的策略、提示词和行为模式

## 项目结构

```
agent-harness/
├── README.md
├── requirements.txt
├── run.bat / run.sh
├── config.yaml
├── agent_harness/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent基类和运行时
│   │   ├── harness.py        # Harness主控制器
│   │   └── lifecycle.py      # 生命周期管理
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── base.py           # 内存基类
│   │   ├── short_term.py     # 短期记忆
│   │   ├── long_term.py      # 长期记忆
│   │   ├── working.py        # 工作记忆
│   │   └── manager.py        # 内存管理器
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── collector.py      # 数据收集器
│   │   ├── metrics.py        # 指标定义
│   │   └── storage.py        # 数据存储
│   ├── evolution/
│   │   ├── __init__.py
│   │   ├── engine.py         # 自进化引擎
│   │   ├── analyzer.py       # 数据分析器
│   │   ├── optimizer.py      # 策略优化器
│   │   └── prompt_tuner.py   # 提示词调优
│   ├── plugins/
│   │   ├── __init__.py
│   │   └── base.py           # 插件基类
│   └── utils/
│       ├── __init__.py
│       ├── config.py         # 配置管理
│       └── logger.py         # 日志工具
├── examples/
│   ├── basic_agent.py        # 基础示例
│   ├── memory_demo.py        # 内存管理示例
│   └── evolution_demo.py     # 自进化示例
├── tests/
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_memory.py
│   └── test_evolution.py
└── data/                     # 运行时数据存储
    ├── telemetry/
    └── evolution/
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基础使用

```python
from agent_harness.core.harness import AgentHarness
from agent_harness.core.agent import BaseAgent
from agent_harness.memory.manager import MemoryManager

# 创建内存管理器
memory = MemoryManager(config={
    "short_term": {"max_size": 100},
    "long_term": {"backend": "sqlite", "path": "data/memory.db"},
    "working": {"max_slots": 7}
})

# 定义Agent
class MyAgent(BaseAgent):
    async def think(self, observation):
        # 从记忆中获取相关上下文
        context = await self.memory.retrieve(observation)
        # 执行推理逻辑
        action = self.llm.generate(observation, context)
        return action

    async def act(self, action):
        # 执行动作
        result = await self.execute(action)
        # 存储到记忆
        await self.memory.store(action, result)
        return result

# 创建Harness并运行
harness = AgentHarness(agent=MyAgent, memory=memory)
harness.run(task="完成指定任务")
```

### 自进化功能

```python
from agent_harness.evolution.engine import EvolutionEngine

# 启用自进化
evolution = EvolutionEngine(
    telemetry_dir="data/telemetry",
    evolution_dir="data/evolution"
)

# 分析运行时数据并生成优化建议
insights = await evolution.analyze()
# 应用优化
await evolution.apply_optimizations(insights)
```

## 配置说明

参见 `config.yaml` 了解完整配置选项。

## 许可证

MIT License