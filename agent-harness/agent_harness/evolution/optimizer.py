"""
Strategy Optimizer for evolution engine.

Optimizes agent strategies based on analysis insights.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json
from pathlib import Path

from agent_harness.evolution.analyzer import AnalysisResult, Insight

logger = logging.getLogger(__name__)


@dataclass
class Optimization:
    """Represents a single optimization change."""
    optimization_type: str
    description: str
    target: str  # What is being optimized
    old_value: Any
    new_value: Any
    confidence: float
    applied: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimization_type": self.optimization_type,
            "description": self.description,
            "target": self.target,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "confidence": self.confidence,
            "applied": self.applied,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OptimizationPlan:
    """A plan containing multiple optimizations."""
    plan_id: str
    optimizations: List[Optimization] = field(default_factory=list)
    based_on: Optional[AnalysisResult] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "optimizations": [o.to_dict() for o in self.optimizations],
            "created_at": self.created_at.isoformat(),
        }


class StrategyOptimizer:
    """
    Optimizes agent strategies based on analysis insights.
    
    Supports:
    - Strategy adaptation
    - Parameter tuning
    - Behavior modification
    - Version control for strategies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.exploration_rate = self.config.get("exploration_rate", 0.2)
        self.storage_path = Path(self.config.get("storage_path", "data/evolution"))
        
        # Strategy versioning
        self.versioning_enabled = self.config.get("versioning", {}).get("enabled", True)
        self.max_versions = self.config.get("versioning", {}).get("max_versions", 10)
        
        # Current strategy
        self._current_strategy: Dict[str, Any] = {}
        self._strategy_versions: List[Dict[str, Any]] = []
        self._optimization_history: List[OptimizationPlan] = []
    
    async def initialize(self) -> None:
        """Initialize the optimizer."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        await self._load_strategy()
        logger.info("Strategy optimizer initialized")
    
    async def _load_strategy(self) -> None:
        """Load current strategy from storage."""
        strategy_file = self.storage_path / "current_strategy.json"
        if strategy_file.exists():
            with open(strategy_file, "r", encoding="utf-8") as f:
                self._current_strategy = json.load(f)
        
        versions_file = self.storage_path / "strategy_versions.json"
        if versions_file.exists():
            with open(versions_file, "r", encoding="utf-8") as f:
                self._strategy_versions = json.load(f)
    
    async def _save_strategy(self) -> None:
        """Save current strategy to storage."""
        strategy_file = self.storage_path / "current_strategy.json"
        with open(strategy_file, "w", encoding="utf-8") as f:
            json.dump(self._current_strategy, f, indent=2, default=str)
        
        if self.versioning_enabled:
            versions_file = self.storage_path / "strategy_versions.json"
            with open(versions_file, "w", encoding="utf-8") as f:
                json.dump(self._strategy_versions[-self.max_versions:], f, indent=2, default=str)
    
    def create_optimization_plan(
        self,
        analysis: AnalysisResult,
        plan_id: Optional[str] = None
    ) -> OptimizationPlan:
        """
        Create an optimization plan based on analysis results.
        
        Args:
            analysis: The analysis result to base optimizations on
            plan_id: Optional plan ID
            
        Returns:
            OptimizationPlan with proposed changes
        """
        import uuid
        plan = OptimizationPlan(
            plan_id=plan_id or str(uuid.uuid4()),
            based_on=analysis
        )
        
        # Generate optimizations based on insights
        for insight in analysis.insights:
            optimizations = self._generate_optimizations_for_insight(insight)
            plan.optimizations.extend(optimizations)
        
        logger.info(f"Created optimization plan {plan.plan_id} with {len(plan.optimizations)} optimizations")
        return plan
    
    def _generate_optimizations_for_insight(self, insight: Insight) -> List[Optimization]:
        """Generate optimizations for a specific insight."""
        optimizations = []
        
        if insight.insight_type == "low_success_rate":
            optimizations.append(Optimization(
                optimization_type="prompt_enhancement",
                description="Enhance prompts for better task understanding",
                target="system_prompt",
                old_value=self._current_strategy.get("system_prompt", ""),
                new_value=self._enhance_prompt(self._current_strategy.get("system_prompt", "")),
                confidence=insight.confidence * 0.8,
            ))
        
        elif insight.insight_type == "inconsistent_performance":
            optimizations.append(Optimization(
                optimization_type="parameter_tuning",
                description="Reduce temperature for more consistent outputs",
                target="temperature",
                old_value=self._current_strategy.get("temperature", 0.7),
                new_value=max(0.3, self._current_strategy.get("temperature", 0.7) - 0.1),
                confidence=insight.confidence * 0.9,
            ))
        
        elif insight.insight_type == "slow_thinking":
            optimizations.append(Optimization(
                optimization_type="context_reduction",
                description="Reduce context window to speed up processing",
                target="max_context_items",
                old_value=self._current_strategy.get("max_context_items", 10),
                new_value=max(5, self._current_strategy.get("max_context_items", 10) - 2),
                confidence=insight.confidence * 0.7,
            ))
        
        elif insight.insight_type == "inefficient_exploration":
            optimizations.append(Optimization(
                optimization_type="strategy_change",
                description="Add early termination for unproductive iterations",
                target="max_iterations",
                old_value=self._current_strategy.get("max_iterations", 100),
                new_value=min(50, self._current_strategy.get("max_iterations", 100)),
                confidence=insight.confidence * 0.8,
            ))
        
        elif insight.insight_type == "dominant_error_type":
            error_type = insight.data.get("error_type", "unknown")
            optimizations.append(Optimization(
                optimization_type="error_handling",
                description=f"Add specific handling for {error_type}",
                target="error_handlers",
                old_value=self._current_strategy.get("error_handlers", {}),
                new_value={
                    **self._current_strategy.get("error_handlers", {}),
                    error_type: {"retry": True, "max_retries": 3}
                },
                confidence=insight.confidence * 0.85,
            ))
        
        return optimizations
    
    def _enhance_prompt(self, prompt: str) -> str:
        """Enhance a prompt based on best practices."""
        enhancements = [
            "Be specific and clear in your reasoning.",
            "Break down complex tasks into smaller steps.",
            "Validate your assumptions before acting.",
        ]
        
        if not prompt:
            return " ".join(enhancements)
        
        # Add enhancements that aren't already present
        for enhancement in enhancements:
            if enhancement.lower() not in prompt.lower():
                prompt += f"\n{enhancement}"
        
        return prompt
    
    async def apply_optimizations(
        self,
        plan: OptimizationPlan,
        auto_apply: bool = False
    ) -> List[Optimization]:
        """
        Apply optimizations from a plan.
        
        Args:
            plan: The optimization plan
            auto_apply: If True, apply all optimizations automatically
            
        Returns:
            List of applied optimizations
        """
        applied = []
        
        # Save current strategy as a version before applying
        if self.versioning_enabled:
            self._strategy_versions.append({
                "strategy": self._current_strategy.copy(),
                "timestamp": datetime.utcnow().isoformat(),
                "plan_id": plan.plan_id,
            })
        
        for optimization in plan.optimizations:
            # Only apply high-confidence optimizations automatically
            if auto_apply and optimization.confidence >= 0.7:
                self._apply_optimization(optimization)
                applied.append(optimization)
            elif not auto_apply:
                # In manual mode, apply all
                self._apply_optimization(optimization)
                applied.append(optimization)
        
        # Save updated strategy
        await self._save_strategy()
        
        # Record in history
        self._optimization_history.append(plan)
        
        logger.info(f"Applied {len(applied)} optimizations from plan {plan.plan_id}")
        return applied
    
    def _apply_optimization(self, optimization: Optimization) -> None:
        """Apply a single optimization."""
        self._current_strategy[optimization.target] = optimization.new_value
        optimization.applied = True
        logger.debug(f"Applied optimization: {optimization.description}")
    
    def get_current_strategy(self) -> Dict[str, Any]:
        """Get the current strategy."""
        return self._current_strategy.copy()
    
    def set_strategy(self, strategy: Dict[str, Any]) -> None:
        """Set the current strategy."""
        self._current_strategy = strategy
    
    async def rollback(self, steps: int = 1) -> bool:
        """
        Rollback strategy to a previous version.
        
        Args:
            steps: Number of versions to rollback
            
        Returns:
            True if rollback was successful
        """
        if not self.versioning_enabled or len(self._strategy_versions) < steps:
            return False
        
        # Remove the last N versions and use the one before
        for _ in range(steps):
            if self._strategy_versions:
                self._strategy_versions.pop()
        
        if self._strategy_versions:
            self._current_strategy = self._strategy_versions[-1]["strategy"].copy()
            await self._save_strategy()
            logger.info(f"Rolled back strategy {steps} version(s)")
            return True
        
        return False
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get optimization history."""
        return [plan.to_dict() for plan in self._optimization_history]
    
    def get_strategy_versions(self) -> List[Dict[str, Any]]:
        """Get strategy version history."""
        return self._strategy_versions.copy()
    
    async def close(self) -> None:
        """Close the optimizer."""
        await self._save_strategy()