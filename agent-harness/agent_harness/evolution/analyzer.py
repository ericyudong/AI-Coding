"""
Data Analyzer for evolution engine.

Analyzes telemetry data to identify patterns and generate insights.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import statistics

logger = logging.getLogger(__name__)


@dataclass
class Insight:
    """Represents an insight from data analysis."""
    insight_type: str
    description: str
    confidence: float  # 0.0 to 1.0
    data: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "insight_type": self.insight_type,
            "description": self.description,
            "confidence": self.confidence,
            "data": self.data,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AnalysisResult:
    """Result of data analysis."""
    insights: List[Insight] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "insights": [i.to_dict() for i in self.insights],
            "metrics": self.metrics,
            "patterns": self.patterns,
            "timestamp": self.timestamp.isoformat(),
        }


class DataAnalyzer:
    """
    Analyzes telemetry data to generate insights for agent evolution.
    
    Analyzes:
    - Success rates and patterns
    - Error patterns and root causes
    - Performance bottlenecks
    - Response quality trends
    - Efficiency metrics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_samples = self.config.get("min_samples", 10)
        self.patterns_to_analyze = self.config.get("patterns", [
            "success_rate",
            "error_patterns",
            "response_quality",
            "efficiency",
        ])
    
    async def analyze(self, sessions: List[Dict[str, Any]]) -> AnalysisResult:
        """
        Analyze session data and generate insights.
        
        Args:
            sessions: List of session data dictionaries
            
        Returns:
            AnalysisResult with insights and patterns
        """
        result = AnalysisResult()
        
        if len(sessions) < self.min_samples:
            logger.info(f"Not enough samples for analysis: {len(sessions)} < {self.min_samples}")
            return result
        
        # Calculate aggregate metrics
        result.metrics = self._calculate_aggregate_metrics(sessions)
        
        # Analyze each pattern type
        if "success_rate" in self.patterns_to_analyze:
            insights = self._analyze_success_rate(sessions)
            result.insights.extend(insights)
        
        if "error_patterns" in self.patterns_to_analyze:
            insights = self._analyze_error_patterns(sessions)
            result.insights.extend(insights)
        
        if "response_quality" in self.patterns_to_analyze:
            insights = self._analyze_response_quality(sessions)
            result.insights.extend(insights)
        
        if "efficiency" in self.patterns_to_analyze:
            insights = self._analyze_efficiency(sessions)
            result.insights.extend(insights)
        
        # Identify patterns
        result.patterns = self._identify_patterns(sessions)
        
        logger.info(f"Analysis complete: {len(result.insights)} insights generated")
        return result
    
    def _calculate_aggregate_metrics(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate metrics across sessions."""
        total_sessions = len(sessions)
        
        # Extract metrics
        success_rates = [s.get("success_rate", 0) for s in sessions]
        error_rates = [s.get("error_rate", 0) for s in sessions]
        durations = [s.get("total_duration_ms", 0) for s in sessions]
        iterations = [s.get("total_iterations", 0) for s in sessions]
        actions = [s.get("total_actions", 0) for s in sessions]
        
        return {
            "total_sessions": total_sessions,
            "avg_success_rate": statistics.mean(success_rates) if success_rates else 0,
            "avg_error_rate": statistics.mean(error_rates) if error_rates else 0,
            "avg_duration_ms": statistics.mean(durations) if durations else 0,
            "avg_iterations": statistics.mean(iterations) if iterations else 0,
            "avg_actions": statistics.mean(actions) if actions else 0,
            "total_errors": sum(s.get("total_errors", 0) for s in sessions),
            "duration_stddev": statistics.stdev(durations) if len(durations) > 1 else 0,
        }
    
    def _analyze_success_rate(self, sessions: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze success rate patterns."""
        insights = []
        
        success_rates = [s.get("success_rate", 0) for s in sessions]
        avg_success = statistics.mean(success_rates)
        
        # Check for low success rate
        if avg_success < 0.7:
            insights.append(Insight(
                insight_type="low_success_rate",
                description=f"Average success rate is low: {avg_success:.2%}",
                confidence=0.8,
                data={"avg_success_rate": avg_success},
                recommendations=[
                    "Review agent prompts for clarity",
                    "Add more context to observations",
                    "Implement better error handling",
                ]
            ))
        
        # Check for high variance
        if len(success_rates) > 1:
            variance = statistics.variance(success_rates)
            if variance > 0.1:
                insights.append(Insight(
                    insight_type="inconsistent_performance",
                    description=f"High variance in success rates: {variance:.3f}",
                    confidence=0.7,
                    data={"variance": variance},
                    recommendations=[
                        "Standardize input processing",
                        "Add validation steps",
                        "Implement retry logic for unstable operations",
                    ]
                ))
        
        # Check for improvement trend
        if len(sessions) >= 5:
            recent = success_rates[-5:]
            older = success_rates[-10:-5] if len(success_rates) >= 10 else success_rates[:5]
            
            if statistics.mean(recent) > statistics.mean(older) + 0.05:
                insights.append(Insight(
                    insight_type="improving_trend",
                    description="Success rate is improving over time",
                    confidence=0.6,
                    data={
                        "recent_avg": statistics.mean(recent),
                        "older_avg": statistics.mean(older),
                    },
                    recommendations=["Continue current strategy"]
                ))
        
        return insights
    
    def _analyze_error_patterns(self, sessions: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze error patterns."""
        insights = []
        
        # Collect all errors
        error_types: Dict[str, int] = {}
        for session in sessions:
            for event in session.get("events", []):
                if event.get("event_type") == "error":
                    error_type = event.get("data", {}).get("error_type", "unknown")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
        
        if error_types:
            # Find most common error
            most_common = max(error_types.items(), key=lambda x: x[1])
            total_errors = sum(error_types.values())
            
            if most_common[1] / total_errors > 0.3:
                insights.append(Insight(
                    insight_type="dominant_error_type",
                    description=f"Most common error: {most_common[0]} ({most_common[1]} occurrences)",
                    confidence=0.85,
                    data={
                        "error_type": most_common[0],
                        "count": most_common[1],
                        "percentage": most_common[1] / total_errors,
                    },
                    recommendations=[
                        f"Add specific handling for {most_common[0]}",
                        "Implement preventive validation",
                    ]
                ))
        
        return insights
    
    def _analyze_response_quality(self, sessions: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze response quality patterns."""
        insights = []
        
        # Analyze think durations
        think_durations = [s.get("avg_think_duration_ms", 0) for s in sessions if s.get("avg_think_duration_ms")]
        
        if think_durations:
            avg_think = statistics.mean(think_durations)
            
            if avg_think > 5000:  # 5 seconds
                insights.append(Insight(
                    insight_type="slow_thinking",
                    description=f"Average thinking time is high: {avg_think:.0f}ms",
                    confidence=0.7,
                    data={"avg_think_duration_ms": avg_think},
                    recommendations=[
                        "Simplify prompts",
                        "Reduce context size",
                        "Consider using a faster model",
                    ]
                ))
        
        return insights
    
    def _analyze_efficiency(self, sessions: List[Dict[str, Any]]) -> List[Insight]:
        """Analyze efficiency patterns."""
        insights = []
        
        # Calculate iterations per success
        for session in sessions:
            iterations = session.get("total_iterations", 0)
            success = session.get("success_rate", 0)
            
            if iterations > 20 and success < 0.5:
                insights.append(Insight(
                    insight_type="inefficient_exploration",
                    description="High iterations with low success suggests inefficient exploration",
                    confidence=0.75,
                    data={
                        "iterations": iterations,
                        "success_rate": success,
                    },
                    recommendations=[
                        "Improve action selection strategy",
                        "Add early termination conditions",
                        "Implement better state evaluation",
                    ]
                ))
                break  # Only report once
        
        return insights
    
    def _identify_patterns(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify behavioral patterns."""
        patterns = {
            "task_types": {},
            "action_sequences": [],
            "common_observations": [],
        }
        
        # Analyze task types
        for session in sessions:
            task = session.get("task", "")
            # Simple categorization by first word
            task_type = task.split()[0].lower() if task else "unknown"
            patterns["task_types"][task_type] = patterns["task_types"].get(task_type, 0) + 1
        
        return patterns
    
    def compare_periods(
        self,
        sessions_a: List[Dict[str, Any]],
        sessions_b: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare two periods of sessions."""
        metrics_a = self._calculate_aggregate_metrics(sessions_a)
        metrics_b = self._calculate_aggregate_metrics(sessions_b)
        
        comparison = {}
        for key in metrics_a:
            if isinstance(metrics_a[key], (int, float)) and isinstance(metrics_b[key], (int, float)):
                if metrics_a[key] != 0:
                    change = (metrics_b[key] - metrics_a[key]) / metrics_a[key]
                    comparison[key] = {
                        "before": metrics_a[key],
                        "after": metrics_b[key],
                        "change": change,
                        "improved": change > 0 if "error" not in key else change < 0,
                    }
        
        return comparison