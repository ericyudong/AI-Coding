"""
Self-Evolution Demo

Demonstrates the self-evolution capabilities of Agent Harness.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_harness.evolution.engine import EvolutionEngine
from agent_harness.evolution.analyzer import DataAnalyzer
from agent_harness.evolution.prompt_tuner import PromptTuner
from agent_harness.utils.logger import setup_logger

logger = setup_logger(level="INFO")


async def main():
    """Run the self-evolution demo."""
    print("=" * 50)
    print("Agent Harness - Self-Evolution Demo")
    print("=" * 50)
    
    # 1. Data Analysis Demo
    print("\n1. Data Analysis...")
    
    analyzer = DataAnalyzer({"min_samples": 3})
    
    # Simulate session data
    mock_sessions = [
        {
            "session_id": f"session-{i}",
            "agent_id": "agent-001",
            "task": f"Task {i}",
            "success_rate": 0.6 + (i * 0.05),
            "error_rate": 0.4 - (i * 0.05),
            "total_duration_ms": 1000 + (i * 100),
            "total_iterations": 5 + i,
            "total_actions": 3 + i,
            "total_errors": 1 if i % 3 == 0 else 0,
            "avg_think_duration_ms": 200,
            "events": [],
        }
        for i in range(10)
    ]
    
    analysis = await analyzer.analyze(mock_sessions)
    
    print(f"  Analyzed {len(mock_sessions)} sessions")
    print(f"  Generated {len(analysis.insights)} insights:")
    for insight in analysis.insights:
        print(f"    - [{insight.insight_type}] {insight.description}")
        print(f"      Confidence: {insight.confidence:.2f}")
    
    print(f"\n  Aggregate metrics:")
    print(f"    Avg success rate: {analysis.metrics.get('avg_success_rate', 0):.2%}")
    print(f"    Avg duration: {analysis.metrics.get('avg_duration_ms', 0):.0f}ms")
    
    # 2. Prompt Tuning Demo
    print("\n2. Prompt Tuning...")
    
    tuner = PromptTuner({
        "learning_rate": 0.1,
        "exploration_rate": 0.2,
        "storage_path": "data/evolution/prompts",
    })
    
    base_prompt = "You are a helpful assistant that answers questions accurately."
    await tuner.initialize(base_prompt)
    
    # Generate variants
    variants = tuner.generate_variants(base_prompt, count=3)
    print(f"  Generated {len(variants)} prompt variants:")
    for i, variant in enumerate(variants):
        print(f"    {i+1}. {variant[:60]}...")
    
    # Simulate usage and record results
    print("\n  Simulating A/B testing...")
    variant_ids = list(tuner._variants.keys())
    
    for vid in variant_ids:
        # Simulate some successes and failures
        for _ in range(5):
            success = vid == variant_ids[0]  # First variant performs better
            await tuner.record_usage(vid, success)
    
    stats = tuner.get_stats()
    print(f"  Prompt tuner stats:")
    print(f"    Total variants: {stats['total_variants']}")
    for vid, vstats in stats['variants'].items():
        print(f"    {vid[:8]}...: score={vstats['performance_score']:.2f}, "
              f"success_rate={vstats['success_rate']:.2%}")
    
    # 3. Evolution Engine Demo
    print("\n3. Evolution Engine...")
    
    engine = EvolutionEngine({
        "storage_path": "data/evolution",
        "analysis": {"min_samples": 3},
        "optimization": {"auto_apply": False},
    })
    
    await engine.initialize()
    
    # Evolve a prompt
    result = await engine.evolve_prompt(base_prompt)
    print(f"  Evolution result: {result['status']}")
    print(f"  Variants created: {result.get('variants_created', 0)}")
    
    # Get evolution stats
    stats = engine.get_stats()
    print(f"\n  Evolution engine stats:")
    print(f"    Evolution count: {stats['evolution_count']}")
    print(f"    Strategy versions: {stats['optimizer']['strategy_versions']}")
    
    await engine.close()
    await tuner.close()
    
    print("\n" + "=" * 50)
    print("Evolution demo completed!")


if __name__ == "__main__":
    asyncio.run(main())