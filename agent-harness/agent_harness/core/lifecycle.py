"""
Lifecycle management for Agent runtime.

Provides state management and lifecycle hooks for agents.
"""

from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    TERMINATED = "terminated"


class LifecycleEvent:
    """Represents a lifecycle event."""
    
    def __init__(
        self,
        event_type: str,
        state: AgentState,
        data: Optional[Dict[str, Any]] = None
    ):
        self.event_type = event_type
        self.state = state
        self.data = data or {}
        self.timestamp = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"LifecycleEvent({self.event_type}, {self.state.value}, {self.timestamp})"


class LifecycleManager:
    """
    Manages the lifecycle of an agent.
    
    Handles state transitions, lifecycle hooks, and event notifications.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS: Dict[AgentState, List[AgentState]] = {
        AgentState.CREATED: [AgentState.INITIALIZING, AgentState.TERMINATED],
        AgentState.INITIALIZING: [AgentState.READY, AgentState.ERROR, AgentState.TERMINATED],
        AgentState.READY: [AgentState.RUNNING, AgentState.STOPPING, AgentState.TERMINATED],
        AgentState.RUNNING: [AgentState.PAUSED, AgentState.STOPPING, AgentState.ERROR],
        AgentState.PAUSED: [AgentState.RUNNING, AgentState.STOPPING, AgentState.ERROR],
        AgentState.STOPPING: [AgentState.STOPPED, AgentState.ERROR],
        AgentState.STOPPED: [AgentState.READY, AgentState.TERMINATED],
        AgentState.ERROR: [AgentState.READY, AgentState.STOPPING, AgentState.TERMINATED],
        AgentState.TERMINATED: [],
    }
    
    def __init__(self):
        self._state = AgentState.CREATED
        self._hooks: Dict[str, List[Callable]] = {
            "on_state_change": [],
            "on_error": [],
            "on_start": [],
            "on_stop": [],
            "on_pause": [],
            "on_resume": [],
        }
        self._history: List[LifecycleEvent] = []
        self._lock = asyncio.Lock()
        self._metadata: Dict[str, Any] = {}
    
    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state
    
    @property
    def history(self) -> List[LifecycleEvent]:
        """Get lifecycle event history."""
        return self._history.copy()
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a lifecycle hook."""
        if event not in self._hooks:
            raise ValueError(f"Unknown lifecycle event: {event}")
        self._hooks[event].append(callback)
    
    def unregister_hook(self, event: str, callback: Callable) -> None:
        """Unregister a lifecycle hook."""
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)
    
    async def _execute_hooks(self, event: str, **kwargs) -> None:
        """Execute all hooks for an event."""
        for callback in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(**kwargs)
                else:
                    callback(**kwargs)
            except Exception as e:
                logger.error(f"Error executing hook {callback} for event {event}: {e}")
    
    async def transition_to(
        self,
        new_state: AgentState,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition to a new state.
        
        Args:
            new_state: The target state
            data: Optional data associated with the transition
            
        Returns:
            True if transition was successful, False otherwise
        """
        async with self._lock:
            if new_state not in self.VALID_TRANSITIONS.get(self._state, []):
                logger.warning(
                    f"Invalid state transition: {self._state.value} -> {new_state.value}"
                )
                return False
            
            old_state = self._state
            self._state = new_state
            
            # Record event
            event = LifecycleEvent(
                event_type="state_change",
                state=new_state,
                data={"from_state": old_state.value, **(data or {})}
            )
            self._history.append(event)
            
            logger.info(f"State transition: {old_state.value} -> {new_state.value}")
            
            # Execute hooks
            await self._execute_hooks(
                "on_state_change",
                old_state=old_state,
                new_state=new_state,
                data=data
            )
            
            # Execute specific event hooks
            if new_state == AgentState.RUNNING and old_state == AgentState.PAUSED:
                await self._execute_hooks("on_resume")
            elif new_state == AgentState.RUNNING:
                await self._execute_hooks("on_start")
            elif new_state == AgentState.PAUSED:
                await self._execute_hooks("on_pause")
            elif new_state in (AgentState.STOPPED, AgentState.TERMINATED):
                await self._execute_hooks("on_stop")
            elif new_state == AgentState.ERROR:
                await self._execute_hooks("on_error", data=data)
            
            return True
    
    async def initialize(self) -> bool:
        """Initialize the agent."""
        return await self.transition_to(AgentState.INITIALIZING)
    
    async def ready(self) -> bool:
        """Mark agent as ready."""
        return await self.transition_to(AgentState.READY)
    
    async def start(self) -> bool:
        """Start the agent."""
        return await self.transition_to(AgentState.RUNNING)
    
    async def pause(self) -> bool:
        """Pause the agent."""
        return await self.transition_to(AgentState.PAUSED)
    
    async def resume(self) -> bool:
        """Resume the agent."""
        return await self.transition_to(AgentState.RUNNING)
    
    async def stop(self) -> bool:
        """Stop the agent."""
        if await self.transition_to(AgentState.STOPPING):
            return await self.transition_to(AgentState.STOPPED)
        return False
    
    async def terminate(self) -> bool:
        """Terminate the agent."""
        return await self.transition_to(AgentState.TERMINATED)
    
    async def error(self, error_data: Optional[Dict[str, Any]] = None) -> bool:
        """Mark agent as errored."""
        return await self.transition_to(AgentState.ERROR, data=error_data)
    
    async def recover(self) -> bool:
        """Recover from error state."""
        if self._state == AgentState.ERROR:
            return await self.transition_to(AgentState.READY)
        return False
    
    async def reset(self) -> bool:
        """Reset agent to ready state from running, stopped or error state."""
        async with self._lock:
            if self._state in (AgentState.RUNNING, AgentState.STOPPED, AgentState.ERROR, AgentState.PAUSED):
                old_state = self._state
                self._state = AgentState.READY
                
                # Record event
                event = LifecycleEvent(
                    event_type="state_change",
                    state=AgentState.READY,
                    data={"from_state": old_state.value, "reset": True}
                )
                self._history.append(event)
                
                logger.info(f"State transition: {old_state.value} -> ready (reset)")
                return True
            return False
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set lifecycle metadata."""
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get lifecycle metadata."""
        return self._metadata.get(key, default)
    
    def get_uptime(self) -> Optional[float]:
        """Get agent uptime in seconds."""
        for event in reversed(self._history):
            if event.state == AgentState.RUNNING:
                return (datetime.utcnow() - event.timestamp).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize lifecycle state to dictionary."""
        return {
            "state": self._state.value,
            "history": [
                {
                    "event_type": e.event_type,
                    "state": e.state.value,
                    "data": e.data,
                    "timestamp": e.timestamp.isoformat()
                }
                for e in self._history
            ],
            "metadata": self._metadata,
        }