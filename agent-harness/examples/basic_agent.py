"""
Basic Agent Example

Demonstrates how to create and run a simple agent using the Agent Harness framework.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_harness.core.agent import BaseAgent, ActionResult
from agent_harness.core.harness import AgentHarness
from agent_harness.utils.logger import setup_logger

# Set up logging
logger = setup_logger(level="INFO")


class SimpleCalculatorAgent(BaseAgent):
    """A simple agent that can perform basic calculations."""
    
    def __init__(self, **kwargs):
        super().__init__(name="calculator-agent", **kwargs)
        self.calculation_history = []
    
    async def think(self, observation):
        """Decide what calculation to perform."""
        task = observation.get("task", "")
        
        # Simple parsing for demonstration
        if "add" in task.lower():
            numbers = self._extract_numbers(task)
            if len(numbers) >= 2:
                return {
                    "action": "add",
                    "numbers": numbers,
                    "finish": False,
                }
        
        elif "multiply" in task.lower() or "times" in task.lower():
            numbers = self._extract_numbers(task)
            if len(numbers) >= 2:
                return {
                    "action": "multiply",
                    "numbers": numbers,
                    "finish": False,
                }
        
        # If we have a result, finish
        if self.calculation_history:
            return {
                "finish": True,
                "result": self.calculation_history[-1],
            }
        
        return {
            "action": "unknown",
            "finish": True,
            "result": "Could not parse the calculation",
        }
    
    async def act(self, thought):
        """Execute the calculation."""
        action = thought.get("action")
        numbers = thought.get("numbers", [])
        
        if action == "add":
            result = sum(numbers)
            self.calculation_history.append(result)
            return ActionResult(
                success=True,
                output=result,
                metadata={"task_complete": True},
            )
        
        elif action == "multiply":
            result = 1
            for n in numbers:
                result *= n
            self.calculation_history.append(result)
            return ActionResult(
                success=True,
                output=result,
                metadata={"task_complete": True},
            )
        
        return ActionResult(
            success=False,
            error=f"Unknown action: {action}",
        )
    
    def _extract_numbers(self, text):
        """Extract numbers from text."""
        import re
        return [int(n) for n in re.findall(r'\d+', text)]


async def main():
    """Run the basic agent example."""
    print("=" * 50)
    print("Agent Harness - Basic Agent Example")
    print("=" * 50)
    
    # Create the agent
    agent = SimpleCalculatorAgent()
    
    # Create harness with minimal config
    config = {
        "memory": {"enabled": True},
        "telemetry": {"enabled": True},
        "evolution": {"enabled": False},
    }
    
    harness = AgentHarness(agent=agent, config=config)
    
    # Initialize
    await harness.initialize()
    
    # Run some tasks
    tasks = [
        "Add 5 and 3",
        "Multiply 4 times 6",
        "Add 10 and 20 and 30",
    ]
    
    for task in tasks:
        print(f"\nTask: {task}")
        result = await harness.run(task)
        print(f"Result: {result}")
    
    # Get status
    print("\n" + "=" * 50)
    print("Final Status:")
    status = harness.get_status()
    print(f"Agent state: {status['agent']['state']}")
    
    # Cleanup
    await harness.shutdown()
    
    print("\nExample completed!")


if __name__ == "__main__":
    asyncio.run(main())