"""
Prompt Tuner for evolution engine.

Automatically tunes prompts based on performance data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    """Represents a prompt variant for A/B testing."""
    variant_id: str
    prompt: str
    version: int = 1
    performance_score: float = 0.0
    usage_count: int = 0
    success_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.success_count / self.usage_count if self.usage_count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant_id": self.variant_id,
            "prompt": self.prompt,
            "version": self.version,
            "performance_score": self.performance_score,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
        }


class PromptTuner:
    """
    Automatically tunes prompts based on performance data.
    
    Features:
    - A/B testing of prompt variants
    - Performance-based selection
    - Automatic prompt generation
    - Version control
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.learning_rate = self.config.get("learning_rate", 0.1)
        self.exploration_rate = self.config.get("exploration_rate", 0.2)
        self.storage_path = Path(self.config.get("storage_path", "data/evolution/prompts"))
        
        # Prompt variants
        self._variants: Dict[str, PromptVariant] = {}
        self._current_variant_id: Optional[str] = None
        self._base_prompt: str = ""
        
        # Templates for prompt generation
        self._templates = {
            "system": [
                "You are a helpful AI assistant. {task_context}",
                "You are an expert agent. {task_context} Be thorough and accurate.",
                "As an AI agent, complete the task efficiently. {task_context}",
            ],
            "reasoning": [
                "Think step by step.",
                "Break down the problem and solve it systematically.",
                "Analyze the situation carefully before responding.",
            ],
            "output_format": [
                "Provide your response in a clear, structured format.",
                "Format your output as JSON with 'action' and 'reasoning' fields.",
                "Respond with a specific action to take.",
            ],
        }
    
    async def initialize(self, base_prompt: str = "") -> None:
        """Initialize the prompt tuner."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._base_prompt = base_prompt
        await self._load_variants()
        
        # Create initial variant if none exists
        if not self._variants:
            await self.create_variant(base_prompt, is_base=True)
        
        logger.info(f"Prompt tuner initialized with {len(self._variants)} variants")
    
    async def _load_variants(self) -> None:
        """Load prompt variants from storage."""
        variants_file = self.storage_path / "prompt_variants.json"
        if variants_file.exists():
            with open(variants_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for variant_id, variant_data in data.get("variants", {}).items():
                    self._variants[variant_id] = PromptVariant(
                        variant_id=variant_data["variant_id"],
                        prompt=variant_data["prompt"],
                        version=variant_data.get("version", 1),
                        performance_score=variant_data.get("performance_score", 0.0),
                        usage_count=variant_data.get("usage_count", 0),
                        success_count=variant_data.get("success_count", 0),
                    )
                self._current_variant_id = data.get("current_variant_id")
    
    async def _save_variants(self) -> None:
        """Save prompt variants to storage."""
        variants_file = self.storage_path / "prompt_variants.json"
        data = {
            "variants": {
                vid: v.to_dict() for vid, v in self._variants.items()
            },
            "current_variant_id": self._current_variant_id,
            "base_prompt": self._base_prompt,
        }
        with open(variants_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    
    async def create_variant(
        self,
        prompt: str,
        is_base: bool = False,
        variant_id: Optional[str] = None
    ) -> str:
        """
        Create a new prompt variant.
        
        Args:
            prompt: The prompt text
            is_base: If True, set as the base variant
            variant_id: Optional variant ID
            
        Returns:
            The variant ID
        """
        import uuid
        vid = variant_id or str(uuid.uuid4())
        
        # Determine version number
        max_version = max([v.version for v in self._variants.values()], default=0)
        
        variant = PromptVariant(
            variant_id=vid,
            prompt=prompt,
            version=max_version + 1,
        )
        
        self._variants[vid] = variant
        
        if is_base or self._current_variant_id is None:
            self._current_variant_id = vid
        
        await self._save_variants()
        logger.info(f"Created prompt variant {vid}")
        return vid
    
    def get_current_prompt(self) -> str:
        """Get the current prompt."""
        if self._current_variant_id and self._current_variant_id in self._variants:
            return self._variants[self._current_variant_id].prompt
        return self._base_prompt
    
    def select_variant(self) -> str:
        """
        Select a variant for use (exploration vs exploitation).
        
        Returns:
            The selected variant ID
        """
        import random
        
        if not self._variants:
            return ""
        
        # Exploration: randomly select a variant
        if random.random() < self.exploration_rate:
            selected = random.choice(list(self._variants.keys()))
        else:
            # Exploitation: select best performing variant
            selected = max(
                self._variants.keys(),
                key=lambda vid: self._variants[vid].performance_score
            )
        
        self._current_variant_id = selected
        return selected
    
    async def record_usage(self, variant_id: str, success: bool) -> None:
        """
        Record usage of a variant.
        
        Args:
            variant_id: The variant that was used
            success: Whether the usage was successful
        """
        if variant_id not in self._variants:
            return
        
        variant = self._variants[variant_id]
        variant.usage_count += 1
        if success:
            variant.success_count += 1
        
        # Update performance score using exponential moving average
        reward = 1.0 if success else 0.0
        variant.performance_score = (
            (1 - self.learning_rate) * variant.performance_score +
            self.learning_rate * reward
        )
        
        await self._save_variants()
    
    def generate_variants(self, base_prompt: str, count: int = 3) -> List[str]:
        """
        Generate new prompt variants from a base prompt.
        
        Args:
            base_prompt: The base prompt to generate from
            count: Number of variants to generate
            
        Returns:
            List of generated prompts
        """
        variants = []
        
        # Template-based generation
        for template_type, templates in self._templates.items():
            for template in templates[:count]:
                if template_type == "system":
                    variant = template.format(task_context=base_prompt)
                else:
                    variant = f"{base_prompt}\n{template}"
                variants.append(variant)
        
        # Mutation-based generation
        mutations = [
            self._add_clarity_instructions,
            self._add_step_by_step,
            self._add_examples_hint,
        ]
        
        for mutation in mutations[:count]:
            variants.append(mutation(base_prompt))
        
        return variants[:count]
    
    def _add_clarity_instructions(self, prompt: str) -> str:
        """Add clarity instructions to prompt."""
        return f"{prompt}\n\nBe specific and clear in your response. Avoid ambiguity."
    
    def _add_step_by_step(self, prompt: str) -> str:
        """Add step-by-step instructions."""
        return f"{prompt}\n\nThink through this step by step before providing your answer."
    
    def _add_examples_hint(self, prompt: str) -> str:
        """Add examples hint."""
        return f"{prompt}\n\nConsider providing examples to illustrate your points."
    
    async def optimize(self) -> Dict[str, Any]:
        """
        Run optimization to find the best prompt variant.
        
        Returns:
            Optimization results
        """
        if not self._variants:
            return {"status": "no_variants"}
        
        # Find best variant
        best_variant = max(
            self._variants.values(),
            key=lambda v: v.performance_score
        )
        
        # Set as current
        self._current_variant_id = best_variant.variant_id
        await self._save_variants()
        
        # Generate new variants for exploration
        new_prompts = self.generate_variants(best_variant.prompt, count=2)
        new_ids = []
        for prompt in new_prompts:
            vid = await self.create_variant(prompt)
            new_ids.append(vid)
        
        return {
            "status": "optimized",
            "best_variant": best_variant.to_dict(),
            "new_variants": new_ids,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get prompt tuner statistics."""
        return {
            "total_variants": len(self._variants),
            "current_variant": self._current_variant_id,
            "variants": {
                vid: {
                    "performance_score": v.performance_score,
                    "success_rate": v.success_rate,
                    "usage_count": v.usage_count,
                }
                for vid, v in self._variants.items()
            },
        }
    
    async def close(self) -> None:
        """Close the prompt tuner."""
        await self._save_variants()