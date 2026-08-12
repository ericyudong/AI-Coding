"""
Telemetry Collector - Main telemetry collection interface.

Collects runtime data from agents for analysis and evolution.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import logging

from agent_harness.telemetry.metrics import Metrics, SessionMetrics
from agent_harness.telemetry.storage import TelemetryStorage

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Main telemetry collector for agent runtime data.
    
    Collects:
    - Actions and their results
    - Thoughts and reasoning
    - Observations
    - Errors and exceptions
    - Performance metrics
    - Memory usage
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        
        # Collection settings
        collection = self.config.get("collection", {})
        self.track_actions = collection.get("track_actions", True)
        self.track_thoughts = collection.get("track_thoughts", True)
        self.track_errors = collection.get("track_errors", True)
        self.track_performance = collection.get("track_performance", True)
        self.track_memory_usage = collection.get("track_memory_usage", True)
        
        # Components
        self.metrics = Metrics()
        self.storage = TelemetryStorage(self.config.get("storage", {}))
        
        # Current session
        self._current_session: Optional[SessionMetrics] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize telemetry collector."""
        await self.storage.initialize()
        self._initialized = True
        logger.info("Telemetry collector initialized")
    
    async def close(self) -> None:
        """Close telemetry collector."""
        await self.storage.close()
        self._initialized = False
    
    async def start_session(self, agent_id: str, task: str) -> str:
        """
        Start a new telemetry session.
        
        Args:
            agent_id: The agent ID
            task: The task being executed
            
        Returns:
            The session ID
        """
        session_id = str(uuid.uuid4())
        
        self._current_session = SessionMetrics(
            session_id=session_id,
            agent_id=agent_id,
            task=task,
        )
        
        self.metrics.record_event("session_start", {
            "session_id": session_id,
            "agent_id": agent_id,
            "task": task,
        })
        
        logger.info(f"Started telemetry session: {session_id}")
        return session_id
    
    async def end_session(self, session_id: str, result: Any = None) -> None:
        """
        End a telemetry session.
        
        Args:
            session_id: The session ID
            result: The final result of the session
        """
        if not self._current_session:
            return
        
        self._current_session.end_time = datetime.utcnow()
        duration = (self._current_session.end_time - self._current_session.start_time).total_seconds() * 1000
        self._current_session.total_duration_ms = duration
        
        # Calculate rates
        if self._current_session.total_actions > 0:
            self._current_session.error_rate = (
                self._current_session.total_errors / self._current_session.total_actions
            )
            self._current_session.success_rate = 1.0 - self._current_session.error_rate
        
        # Store custom result
        self._current_session.custom["result"] = str(result)[:1000] if result else None
        
        # Save session
        await self.storage.save_session(self._current_session)
        
        self.metrics.record_event("session_end", {
            "session_id": session_id,
            "duration_ms": duration,
            "iterations": self._current_session.total_iterations,
            "actions": self._current_session.total_actions,
            "errors": self._current_session.total_errors,
        })
        
        logger.info(f"Ended telemetry session: {session_id}, duration: {duration:.2f}ms")
        self._current_session = None
    
    async def record_observation(
        self,
        agent_id: str,
        observation: Any,
        iteration: int
    ) -> None:
        """Record an observation."""
        if not self.enabled or not self._current_session:
            return
        
        self._current_session.total_iterations = iteration
        
        await self.storage.add_event(
            self._current_session.session_id,
            "observation",
            {
                "iteration": iteration,
                "observation": str(observation)[:500],
            }
        )
    
    async def record_thought(
        self,
        agent_id: str,
        thought: Any,
        duration_ms: float
    ) -> None:
        """Record a thought/reasoning step."""
        if not self.enabled or not self._current_session:
            return
        
        if self.track_thoughts:
            self._current_session.total_thoughts += 1
            
            # Update average think duration
            n = self._current_session.total_thoughts
            self._current_session.avg_think_duration_ms = (
                (self._current_session.avg_think_duration_ms * (n - 1) + duration_ms) / n
            )
            
            await self.storage.add_event(
                self._current_session.session_id,
                "thought",
                {
                    "thought": str(thought)[:500],
                    "duration_ms": duration_ms,
                }
            )
        
        if self.track_performance:
            self.metrics.record_duration("think_duration", duration_ms)
    
    async def record_action(
        self,
        agent_id: str,
        action: Any,
        result: Any,
        duration_ms: float
    ) -> None:
        """Record an action and its result."""
        if not self.enabled or not self._current_session:
            return
        
        if self.track_actions:
            self._current_session.total_actions += 1
            
            # Update average act duration
            n = self._current_session.total_actions
            self._current_session.avg_act_duration_ms = (
                (self._current_session.avg_act_duration_ms * (n - 1) + duration_ms) / n
            )
            
            # Check if action was successful
            success = True
            if hasattr(result, "success"):
                success = result.success
            elif isinstance(result, dict):
                success = result.get("success", True)
            
            if not success:
                self._current_session.total_errors += 1
            
            await self.storage.add_event(
                self._current_session.session_id,
                "action",
                {
                    "action": str(action)[:500],
                    "result": str(result)[:500],
                    "success": success,
                    "duration_ms": duration_ms,
                }
            )
        
        if self.track_performance:
            self.metrics.record_duration("act_duration", duration_ms)
            self.metrics.record_counter("actions_total")
    
    async def record_error(
        self,
        agent_id: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an error."""
        if not self.enabled or not self._current_session:
            return
        
        if self.track_errors:
            self._current_session.total_errors += 1
            
            await self.storage.add_event(
                self._current_session.session_id,
                "error",
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error)[:500],
                    "context": context or {},
                }
            )
        
        self.metrics.record_counter("errors_total", labels={"type": type(error).__name__})
    
    async def record_memory_operation(
        self,
        operation: str,
        memory_type: str,
        count: int = 1
    ) -> None:
        """Record a memory operation."""
        if not self.enabled or not self._current_session:
            return
        
        if self.track_memory_usage:
            if operation == "store":
                self._current_session.memory_stores += count
            elif operation == "retrieve":
                self._current_session.memory_retrievals += count
            
            self.metrics.record_counter(
                "memory_operations",
                count,
                labels={"operation": operation, "type": memory_type}
            )
    
    async def record_custom_metric(
        self,
        name: str,
        value: Any,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a custom metric."""
        if not self.enabled:
            return
        
        self.metrics.record_event(name, {"value": value}, labels)
    
    async def flush(self) -> None:
        """Flush any pending telemetry data."""
        if self._current_session:
            await self.storage.save_session(self._current_session)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics."""
        return {
            "enabled": self.enabled,
            "current_session": self._current_session.session_id if self._current_session else None,
            "metrics_summary": self.metrics.summary(),
            "storage_stats": self.storage.get_stats(),
        }
    
    async def get_session_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get session history."""
        sessions = await self.storage.list_sessions(agent_id, limit)
        return [s.to_dict() for s in sessions]
    
    async def export_data(self, path: str) -> None:
        """Export all telemetry data."""
        import json
        
        data = {
            "sessions": await self.get_session_history(),
            "metrics": self.metrics.get_all_metrics(),
            "export_time": datetime.utcnow().isoformat(),
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Telemetry data exported to {path}")