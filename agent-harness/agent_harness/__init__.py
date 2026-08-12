"""
Agent Harness Framework

A comprehensive framework for agent runtime management, memory management,
and self-evolution capabilities.
"""

__version__ = "0.1.0"
__author__ = "Agent Harness Team"

from agent_harness.core.agent import BaseAgent
from agent_harness.core.harness import AgentHarness
from agent_harness.memory.manager import MemoryManager

__all__ = [
    "BaseAgent",
    "AgentHarness",
    "MemoryManager",
    "__version__",
]