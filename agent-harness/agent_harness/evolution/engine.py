"""
Evolution Engine - Main self-evolution controller.

Coordinates analysis, optimization, and prompt tuning for agent self-improvement.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json
from pathlib import Path

from agent_harness.evolution.analyzer import DataAnalyzer, AnalysisResult
from agent_harness.evolution.optimizer import StrategyOptimizer, OptimizationPlan
from agent_harness.evolution.prompt_tuner import PromptTuner

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Main evolution engine for agent self-improvement.
    
    Coordinates:
    - Data analysis from telemetry
    - Strategy optimization
    - Prompt tuning
    - Performance tracking
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        telemetry=None
    ):
        self.config = config or {}
        self.telemetry = telemetry
        self.storage_path = Path(self.config.get("storage_path", "data/evolution"))
        
        # Analysis settings
        analysis_config = self.config.get("analysis", {})
        self.min_samples = analysis_config.get("min_samples", 10)
        self.analysis_interval = analysis_config.get("analysis_interval", 3600)
        
        # Optimization settings
        optimization_config = self.config.get("optimization", {})
        self.auto_apply = optimization_config.get("auto_apply", False)
        
        # Components
        self.analyzer = DataAnalyzer(analysis_config)
        self.optimizer = StrategyOptimizer({
            **optimization_config,
            "storage_path": str(self.storage_path),
        })
        self.prompt_tuner = PromptTuner({
            **optimization_config,
            "storage_path": str(self.storage_path / "prompts"),
        })
        
        # State
        self._initialized = False
        self._last_analysis_time: Optional[datetime] = None
        self._evolution_history: List[Dict[str, Any]] = []
    
    async def initialize(self) -> None:
        """Initialize the evolution engine."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        await self.optimizer.initialize()
        await self.prompt_tuner.initialize()
        
        # Load evolution history
        history_file = self.storage_path / "evolution_history.json"
        if history_file.exists():
            with open(history_file, "r", encoding="utf-8") as f:
                self._evolution_history = json.load(f)
        
        self._initialized = True
        logger.info("Evolution engine initialized")
    
    async def close(self) -> None:
        """Close the evolution engine."""
        await self.optimizer.close()
        await self.prompt_tuner.close()
        
        # Save evolution history
        history_file = self.storage_path / "evolution_history.json"
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(self._evolution_history, f, indent=2, default=str)
        
        self._initialized = False
    
    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze telemetry data and generate insights.
        
        Returns:
            Analysis results with insights and recommendations
        """
        if not self.telemetry:
            logger.warning("No telemetry source configured")
            return {"status": "no_telemetry", "insights": []}
        
        # Get session history from telemetry
        sessions = await self.telemetry.get_session_history(limit=100)
        
        if len(sessions) < self.min_samples:
            logger.info(f"Not enough sessions for analysis: {len(sessions)} < {self.min_samples}")
            return {
                "status": "insufficient_data",
                "sessions": len(sessions),
                "required": self.min_samples,
            }
        
        # Run analysis
        analysis_result = await self.analyzer.analyze(sessions)
        
        self._last_analysis_time = datetime.utcnow()
        
        return {
            "status": "success",
            "analysis": analysis_result.to_dict(),
            "timestamp": self._last_analysis_time.isoformat(),
        }
    
    async def apply_optimizations(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply optimizations based on analysis results.
        
        Args:
            analysis: Analysis results from analyze()
            
        Returns:
            Optimization results
        """
        if analysis.get("status") != "success":
            return {"status": "no_analysis", "applied": []}
        
        # Reconstruct AnalysisResult
        analysis_data = analysis.get("analysis", {})
        analysis_result = AnalysisResult(
            metrics=analysis_data.get("metrics", {}),
            patterns=analysis_data.get("patterns", {}),
        )
        
        # Reconstruct insights
        from agent_harness.evolution.analyzer import Insight
        for insight_data in analysis_data.get("insights", []):
            analysis_result.insights.append(Insight(
                insight_type=insight_data["insight_type"],
                description=insight_data["description"],
                confidence=insight_data["confidence"],
                data=insight_data.get("data", {}),
                recommendations=insight_data.get("recommendations", []),
            ))
        
        # Create optimization plan
        plan = self.optimizer.create_optimization_plan(analysis_result)
        
        # Apply optimizations
        applied = await self.optimizer.apply_optimizations(plan, self.auto_apply)
        
        # Record in evolution history
        self._evolution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "plan_id": plan.plan_id,
            "insights_count": len(analysis_result.insights),
            "optimizations_applied": len(applied),
            "auto_apply": self.auto_apply,
        })
        
        return {
            "status": "success",
            "plan_id": plan.plan_id,
            "applied": [o.to_dict() for o in applied],
            "total_optimizations": len(plan.optimizations),
        }
    
    async def on_session_complete(self, session_id: str) -> None:
        """
        Handle session completion event.
        
        Args:
            session_id: The completed session ID
        """
        # Check if it's time for analysis
        if self._last_analysis_time:
            elapsed = (datetime.utcnow() - self._last_analysis_time).total_seconds()
            if elapsed < self.analysis_interval:
                return
        else:
            # First session, wait for more data
            return
        
        # Trigger analysis
        logger.info("Triggering automatic evolution analysis")
        analysis = await self.analyze()
        
        if analysis.get("status") == "success":
            await self.apply_optimizations(analysis)
    
    async def evolve_prompt(self, base_prompt: str) -> Dict[str, Any]:
        """
        Evolve a prompt using the prompt tuner.
        
        Args:
            base_prompt: The base prompt to evolve
            
        Returns:
            Evolution results
        """
        # Initialize prompt tuner with base prompt
        await self.prompt_tuner.initialize(base_prompt)
        
        # Generate variants
        variants = self.prompt_tuner.generate_variants(base_prompt, count=5)
        
        # Create variants
        variant_ids = []
        for variant in variants:
            vid = await self.prompt_tuner.create_variant(variant)
            variant_ids.append(vid)
        
        return {
            "status": "success",
            "base_prompt": base_prompt,
            "variants_created": len(variant_ids),
            "variant_ids": variant_ids,
        }
    
    def get_current_strategy(self) -> Dict[str, Any]:
        """Get the current optimized strategy."""
        return self.optimizer.get_current_strategy()
    
    def get_current_prompt(self) -> str:
        """Get the current optimized prompt."""
        return self.prompt_tuner.get_current_prompt()
    
    async def rollback(self, steps: int = 1) -> bool:
        """
        Rollback to a previous strategy version.
        
        Args:
            steps: Number of versions to rollback
            
        Returns:
            True if rollback was successful
        """
        return await self.optimizer.rollback(steps)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get evolution engine statistics."""
        return {
            "initialized": self._initialized,
            "last_analysis": self._last_analysis_time.isoformat() if self._last_analysis_time else None,
            "evolution_count": len(self._evolution_history),
            "optimizer": {
                "strategy_versions": len(self.optimizer.get_strategy_versions()),
                "optimization_history": len(self.optimizer.get_optimization_history()),
            },
            "prompt_tuner": self.prompt_tuner.get_stats(),
        }
    
    def get_evolution_history(self) -> List[Dict[str, Any]]:
        """Get evolution history."""
        return self._evolution_history.copy()
    
    async def export_state(self, path: str) -> None:
        """Export evolution state to file."""
        state = {
            "strategy": self.optimizer.get_current_strategy(),
            "strategy_versions": self.optimizer.get_strategy_versions(),
            "prompt_tuner": self.prompt_tuner.get_stats(),
            "evolution_history": self._evolution_history,
            "export_time": datetime.utcnow().isoformat(),
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"Evolution state exported to {path}")
    
    async def import_state(self, path: str) -> None:
        """Import evolution state from file."""
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        if state.get("strategy"):
            self.optimizer.set_strategy(state["strategy"])
        
        if state.get("evolution_history"):
            self._evolution_history = state["evolution_history"]
        
        logger.info(f"Evolution state imported from {path}")