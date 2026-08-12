"""
Base Agent implementation for Agent Harness framework.

Provides the abstract base class and runtime for agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import uuid
import logging

from agent_harness.core.lifecycle import LifecycleManager, AgentState

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a message in the agent's context."""
    role: str  # system, user, assistant, tool
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ActionResult:
    """Result of an agent action."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class AgentContext:
    """Context for agent execution."""
    task: str
    messages: List[Message] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 100


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides the core agent interface and runtime functionality.
    Subclasses should implement the think() and act() methods.
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = str(uuid.uuid4())
        self.name = name or f"agent-{self.agent_id[:8]}"
        self.config = config or {}
        self.lifecycle = LifecycleManager()
        
        # Runtime components (set by harness)
        self._memory = None
        self._telemetry = None
        self._tools: Dict[str, Callable] = {}
        
        # Execution state
        self._context: Optional[AgentContext] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "on_think": [],
            "on_act": [],
            "on_observe": [],
            "on_error": [],
            "on_complete": [],
        }
    
    @property
    def memory(self):
        """Get the memory manager."""
        return self._memory
    
    @memory.setter
    def memory(self, value):
        """Set the memory manager."""
        self._memory = value
    
    @property
    def telemetry(self):
        """Get the telemetry collector."""
        return self._telemetry
    
    @telemetry.setter
    def telemetry(self, value):
        """Set the telemetry collector."""
        self._telemetry = value
    
    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self.lifecycle.state
    
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for the agent to use."""
        self._tools[name] = func
        logger.info(f"Registered tool: {name}")
    
    def unregister_tool(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a registered tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def on(self, event: str, callback: Callable) -> None:
        """Register an event callback."""
        if event not in self._callbacks:
            raise ValueError(f"Unknown event: {event}")
        self._callbacks[event].append(callback)
    
    async def _emit(self, event: str, **kwargs) -> None:
        """Emit an event to registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(**kwargs)
                else:
                    callback(**kwargs)
            except Exception as e:
                logger.error(f"Error in callback for event {event}: {e}")
    
    async def initialize(self) -> None:
        """Initialize the agent."""
        await self.lifecycle.initialize()
        await self._on_initialize()
        await self.lifecycle.ready()
        logger.info(f"Agent {self.name} initialized")
    
    async def _on_initialize(self) -> None:
        """Hook for subclass initialization."""
        pass
    
    async def run(self, task: str, **kwargs) -> Any:
        """
        Run the agent on a task.
        
        Args:
            task: The task description
            **kwargs: Additional context variables
            
        Returns:
            The final result of the agent's execution
        """
        if self.state != AgentState.READY:
            raise RuntimeError(f"Agent not ready, current state: {self.state}")
        
        await self.lifecycle.start()
        self._running = True
        
        # Create execution context
        self._context = AgentContext(
            task=task,
            variables=kwargs,
            max_iterations=self.config.get("max_iterations", 100)
        )
        
        # Add initial message
        self._context.messages.append(Message(role="user", content=task))
        
        try:
            result = await self._execute_loop()
            await self._emit("on_complete", result=result)
            return result
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            await self._emit("on_error", error=e)
            await self.lifecycle.error({"error": str(e)})
            raise
        finally:
            self._running = False
            # Reset to ready state for next run
            await self.lifecycle.reset()
    
    async def _execute_loop(self) -> Any:
        """Main execution loop."""
        result = None
        
        while (
            self._running and
            self._context.iteration < self._context.max_iterations and
            self.state == AgentState.RUNNING
        ):
            self._context.iteration += 1
            
            # Observe - get current state/observation
            observation = await self.observe()
            await self._emit("on_observe", observation=observation)
            
            # Record telemetry
            if self._telemetry:
                await self._telemetry.record_observation(
                    self.agent_id,
                    observation,
                    self._context.iteration
                )
            
            # Think - decide what to do
            start_time = datetime.utcnow()
            thought = await self.think(observation)
            think_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            await self._emit("on_think", thought=thought)
            
            if self._telemetry:
                await self._telemetry.record_thought(
                    self.agent_id,
                    thought,
                    think_duration
                )
            
            # Check if agent wants to finish
            if self._should_finish(thought):
                result = self._extract_result(thought)
                break
            
            # Act - execute the decided action
            start_time = datetime.utcnow()
            action_result = await self.act(thought)
            act_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            await self._emit("on_act", action=thought, result=action_result)
            
            if self._telemetry:
                await self._telemetry.record_action(
                    self.agent_id,
                    thought,
                    action_result,
                    act_duration
                )
            
            # Store in memory
            if self._memory:
                await self._memory.store({
                    "iteration": self._context.iteration,
                    "observation": observation,
                    "thought": thought,
                    "action_result": action_result.__dict__ if hasattr(action_result, "__dict__") else action_result,
                })
            
            # Check if action completed the task
            if action_result.success and self._is_task_complete(action_result):
                result = action_result.output
                break
        
        return result
    
    @abstractmethod
    async def think(self, observation: Any) -> Any:
        """
        Think about what to do next.
        
        Args:
            observation: Current observation/state
            
        Returns:
            The decided action or thought
        """
        pass
    
    @abstractmethod
    async def act(self, thought: Any) -> ActionResult:
        """
        Execute an action based on thought.
        
        Args:
            thought: The thought/action to execute
            
        Returns:
            Result of the action
        """
        pass
    
    async def observe(self) -> Any:
        """
        Get current observation.
        
        Override this method to customize observation gathering.
        """
        return {
            "task": self._context.task,
            "iteration": self._context.iteration,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in self._context.messages[-10:]  # Last 10 messages
            ],
            "variables": self._context.variables,
        }
    
    def _should_finish(self, thought: Any) -> bool:
        """Check if the agent should finish."""
        if isinstance(thought, dict):
            return thought.get("finish", False)
        return False
    
    def _extract_result(self, thought: Any) -> Any:
        """Extract the final result from thought."""
        if isinstance(thought, dict):
            return thought.get("result")
        return thought
    
    def _is_task_complete(self, result: ActionResult) -> bool:
        """Check if the task is complete."""
        return result.metadata.get("task_complete", False)
    
    async def pause(self) -> None:
        """Pause the agent."""
        await self.lifecycle.pause()
        self._running = False
    
    async def resume(self) -> None:
        """Resume the agent."""
        await self.lifecycle.resume()
        self._running = True
    
    async def stop(self) -> None:
        """Stop the agent."""
        self._running = False
        await self.lifecycle.stop()
    
    def add_message(self, role: str, content: str, **metadata) -> Message:
        """Add a message to the context."""
        msg = Message(role=role, content=content, metadata=metadata)
        if self._context:
            self._context.messages.append(msg)
        return msg
    
    def get_context(self) -> Optional[AgentContext]:
        """Get current execution context."""
        return self._context
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "state": self.state.value,
            "config": self.config,
            "tools": list(self._tools.keys()),
            "lifecycle": self.lifecycle.to_dict(),
        }