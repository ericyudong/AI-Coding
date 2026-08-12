"""
Agent Harness - Main controller for agent execution.

Provides the orchestration layer that manages agents, memory, telemetry,
and evolution components.
"""

from typing import Any, Dict, List, Optional, Type, Union
from pathlib import Path
import asyncio
import logging
import yaml

from agent_harness.core.agent import BaseAgent
from agent_harness.core.lifecycle import AgentState

logger = logging.getLogger(__name__)


class AgentHarness:
    """
    Main harness controller for managing agent execution.
    
    The harness provides:
    - Agent lifecycle management
    - Memory management integration
    - Telemetry collection
    - Self-evolution capabilities
    - Plugin system
    """
    
    def __init__(
        self,
        agent: Optional[Union[BaseAgent, Type[BaseAgent]]] = None,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None
    ):
        # Load configuration
        if config_path:
            config = self._load_config(config_path)
        self.config = config or {}
        
        # Initialize agent
        if isinstance(agent, type):
            self.agent = agent(config=self.config.get("agent", {}))
        else:
            self.agent = agent
        
        # Components (lazy initialization)
        self._memory = None
        self._telemetry = None
        self._evolution = None
        self._plugins: List[Any] = []
        
        # Execution state
        self._initialized = False
        self._running = False
    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_path = Path(path)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        logger.warning(f"Config file not found: {path}")
        return {}
    
    @property
    def memory(self):
        """Get or create memory manager."""
        if self._memory is None:
            from agent_harness.memory.manager import MemoryManager
            self._memory = MemoryManager(self.config.get("memory", {}))
        return self._memory
    
    @property
    def telemetry(self):
        """Get or create telemetry collector."""
        if self._telemetry is None:
            from agent_harness.telemetry.collector import TelemetryCollector
            self._telemetry = TelemetryCollector(self.config.get("telemetry", {}))
        return self._telemetry
    
    @property
    def evolution(self):
        """Get or create evolution engine."""
        if self._evolution is None:
            from agent_harness.evolution.engine import EvolutionEngine
            self._evolution = EvolutionEngine(
                config=self.config.get("evolution", {}),
                telemetry=self.telemetry
            )
        return self._evolution
    
    async def initialize(self) -> None:
        """Initialize the harness and all components."""
        if self._initialized:
            return
        
        logger.info("Initializing Agent Harness...")
        
        # Initialize memory
        if self.config.get("memory", {}).get("enabled", True):
            await self.memory.initialize()
            logger.info("Memory manager initialized")
        
        # Initialize telemetry
        if self.config.get("telemetry", {}).get("enabled", True):
            await self.telemetry.initialize()
            logger.info("Telemetry collector initialized")
        
        # Initialize evolution
        if self.config.get("evolution", {}).get("enabled", False):
            await self.evolution.initialize()
            logger.info("Evolution engine initialized")
        
        # Load plugins
        await self._load_plugins()
        
        # Initialize agent
        if self.agent:
            self.agent.memory = self.memory
            self.agent.telemetry = self.telemetry
            await self.agent.initialize()
            logger.info(f"Agent {self.agent.name} initialized")
        
        self._initialized = True
        logger.info("Agent Harness initialized successfully")
    
    async def _load_plugins(self) -> None:
        """Load plugins from configuration."""
        plugin_config = self.config.get("plugins", {})
        if not plugin_config.get("auto_load", False):
            return
        
        plugin_dir = Path(plugin_config.get("directory", "plugins"))
        if not plugin_dir.exists():
            return
        
        # Plugin loading logic can be extended here
        logger.info(f"Loading plugins from {plugin_dir}")
    
    def set_agent(self, agent: Union[BaseAgent, Type[BaseAgent]]) -> None:
        """Set or replace the agent."""
        if isinstance(agent, type):
            self.agent = agent(config=self.config.get("agent", {}))
        else:
            self.agent = agent
        
        if self._initialized:
            self.agent.memory = self.memory
            self.agent.telemetry = self.telemetry
    
    async def run(self, task: str, **kwargs) -> Any:
        """
        Run the agent on a task.
        
        Args:
            task: The task description
            **kwargs: Additional context variables
            
        Returns:
            The result of the agent's execution
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.agent:
            raise RuntimeError("No agent configured")
        
        self._running = True
        
        try:
            # Start telemetry session
            session_id = await self.telemetry.start_session(
                self.agent.agent_id,
                task
            )
            
            # Run the agent
            result = await self.agent.run(task, **kwargs)
            
            # End telemetry session
            await self.telemetry.end_session(session_id, result)
            
            # Trigger evolution analysis if enabled
            if self.config.get("evolution", {}).get("enabled", False):
                await self.evolution.on_session_complete(session_id)
            
            return result
            
        finally:
            self._running = False
    
    async def run_batch(self, tasks: List[str], **kwargs) -> List[Any]:
        """Run multiple tasks sequentially."""
        results = []
        for task in tasks:
            result = await self.run(task, **kwargs)
            results.append(result)
        return results
    
    async def run_parallel(self, tasks: List[str], **kwargs) -> List[Any]:
        """Run multiple tasks in parallel (requires multiple agents)."""
        # This would require agent pooling - simplified for now
        return await asyncio.gather(*[self.run(task, **kwargs) for task in tasks])
    
    async def pause(self) -> None:
        """Pause the agent."""
        if self.agent:
            await self.agent.pause()
    
    async def resume(self) -> None:
        """Resume the agent."""
        if self.agent:
            await self.agent.resume()
    
    async def stop(self) -> None:
        """Stop the agent and cleanup."""
        self._running = False
        
        if self.agent:
            await self.agent.stop()
        
        if self._telemetry:
            await self._telemetry.flush()
        
        logger.info("Agent Harness stopped")
    
    async def shutdown(self) -> None:
        """Shutdown the harness and all components."""
        await self.stop()
        
        if self._memory:
            await self._memory.close()
        
        if self._telemetry:
            await self._telemetry.close()
        
        if self._evolution:
            await self._evolution.close()
        
        self._initialized = False
        logger.info("Agent Harness shutdown complete")
    
    async def trigger_evolution(self) -> Dict[str, Any]:
        """Manually trigger evolution analysis and optimization."""
        if not self._evolution:
            raise RuntimeError("Evolution engine not enabled")
        
        insights = await self.evolution.analyze()
        
        if self.config.get("evolution", {}).get("optimization", {}).get("auto_apply", False):
            await self.evolution.apply_optimizations(insights)
        
        return insights
    
    def get_status(self) -> Dict[str, Any]:
        """Get current harness status."""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "agent": self.agent.to_dict() if self.agent else None,
            "memory_stats": self._memory.get_stats() if self._memory else None,
            "telemetry_stats": self._telemetry.get_stats() if self._telemetry else None,
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if self._memory:
            return self._memory.get_stats()
        return {}
    
    def get_telemetry_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics."""
        if self._telemetry:
            return self._telemetry.get_stats()
        return {}
    
    async def export_state(self, path: str) -> None:
        """Export harness state to file."""
        import json
        
        state = {
            "config": self.config,
            "status": self.get_status(),
            "memory": await self._memory.export() if self._memory else None,
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"State exported to {path}")
    
    async def import_state(self, path: str) -> None:
        """Import harness state from file."""
        import json
        
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        if state.get("memory") and self._memory:
            await self._memory.import_data(state["memory"])
        
        logger.info(f"State imported from {path}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.get_event_loop().run_until_complete(self.shutdown())
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()