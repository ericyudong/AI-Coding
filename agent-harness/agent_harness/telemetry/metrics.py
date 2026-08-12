"""
Metrics definitions for telemetry.

Defines metric types and metric data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    DURATION = "duration"
    EVENT = "event"


@dataclass
class Metric:
    """Represents a single metric data point."""
    name: str
    value: Any
    metric_type: MetricType = MetricType.GAUGE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    labels: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "unit": self.unit,
        }


@dataclass
class SessionMetrics:
    """Metrics for a single agent session."""
    session_id: str
    agent_id: str
    task: str
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    # Counters
    total_iterations: int = 0
    total_actions: int = 0
    total_errors: int = 0
    total_thoughts: int = 0
    
    # Durations (in milliseconds)
    total_duration_ms: float = 0.0
    avg_think_duration_ms: float = 0.0
    avg_act_duration_ms: float = 0.0
    
    # Quality metrics
    success_rate: float = 0.0
    error_rate: float = 0.0
    
    # Memory metrics
    memory_stores: int = 0
    memory_retrievals: int = 0
    
    # Custom metrics
    custom: Dict[str, Any] = field(default_factory=dict)
    
    # Event log
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task": self.task,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_iterations": self.total_iterations,
            "total_actions": self.total_actions,
            "total_errors": self.total_errors,
            "total_thoughts": self.total_thoughts,
            "total_duration_ms": self.total_duration_ms,
            "avg_think_duration_ms": self.avg_think_duration_ms,
            "avg_act_duration_ms": self.avg_act_duration_ms,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "memory_stores": self.memory_stores,
            "memory_retrievals": self.memory_retrievals,
            "custom": self.custom,
            "events": self.events,
        }


class Metrics:
    """
    Metrics collection and aggregation.
    
    Provides methods for recording and aggregating metrics.
    """
    
    def __init__(self):
        self._metrics: List[Metric] = []
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
    
    def record_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a counter increment."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.COUNTER,
            labels=labels or {}
        )
        self._metrics.append(metric)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            labels=labels or {}
        )
        self._metrics.append(metric)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.HISTOGRAM,
            labels=labels or {}
        )
        self._metrics.append(metric)
    
    def record_duration(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a duration metric."""
        self.record_histogram(name, duration_ms, labels)
    
    def record_event(self, name: str, data: Optional[Dict[str, Any]] = None, labels: Optional[Dict[str, str]] = None) -> None:
        """Record an event."""
        metric = Metric(
            name=name,
            value=data or {},
            metric_type=MetricType.EVENT,
            labels=labels or {}
        )
        self._metrics.append(metric)
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get a counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get a gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[min(int(count * 0.95), count - 1)],
            "p99": sorted_values[min(int(count * 0.99), count - 1)],
        }
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get all recorded metrics."""
        return [m.to_dict() for m in self._metrics]
    
    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                key: self.get_histogram_stats(key.split("[")[0])
                for key in self._histograms.keys()
            },
            "total_metrics": len(self._metrics),
        }