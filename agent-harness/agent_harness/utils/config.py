"""
Configuration management utilities.

Provides configuration loading, validation, and management.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import os
import yaml
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Configuration manager for Agent Harness.
    
    Supports:
    - YAML configuration files
    - Environment variable overrides
    - Default values
    - Configuration validation
    """
    
    DEFAULT_CONFIG = {
        "agent": {
            "name": "default-agent",
            "max_iterations": 100,
            "timeout": 300,
        },
        "memory": {
            "short_term": {"enabled": True, "max_size": 100},
            "working": {"enabled": True, "max_slots": 7},
            "long_term": {"enabled": True, "backend": "file"},
        },
        "telemetry": {
            "enabled": True,
            "storage": {"backend": "file"},
        },
        "evolution": {
            "enabled": False,
        },
        "logging": {
            "level": "INFO",
        },
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._config_path = config_path
        
        # Load default config
        self._config = self.DEFAULT_CONFIG.copy()
        
        # Load from file if provided
        if config_path:
            self.load(config_path)
        
        # Apply environment overrides
        self._apply_env_overrides()
    
    def load(self, path: str) -> None:
        """Load configuration from a YAML file."""
        config_path = Path(path)
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {path}")
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
            
            # Deep merge with defaults
            self._config = self._deep_merge(self._config, file_config)
            logger.info(f"Configuration loaded from {path}")
        except Exception as e:
            logger.error(f"Error loading config from {path}: {e}")
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Map environment variables to config paths
        env_mappings = {
            "AGENT_HARNESS_LOG_LEVEL": ("logging", "level"),
            "AGENT_HARNESS_TELEMETRY_ENABLED": ("telemetry", "enabled"),
            "AGENT_HARNESS_EVOLUTION_ENABLED": ("evolution", "enabled"),
            "OPENAI_API_KEY": ("llm", "api_key"),
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                self.set(config_path, self._parse_env_value(value))
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value."""
        # Boolean
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
        
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        
        return value
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by path.
        
        Args:
            path: Dot-separated path (e.g., "memory.short_term.max_size")
            default: Default value if not found
            
        Returns:
            The configuration value
        """
        keys = path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, path: tuple, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            path: Tuple of keys (e.g., ("memory", "short_term", "max_size"))
            value: The value to set
        """
        config = self._config
        
        for key in path[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[path[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        return self._config.get(section, {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Get the full configuration as a dictionary."""
        return self._config.copy()
    
    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to a YAML file."""
        save_path = Path(path or self._config_path or "config.yaml")
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Error saving config to {save_path}: {e}")
    
    def validate(self) -> bool:
        """Validate the configuration."""
        # Basic validation
        required_sections = ["agent", "memory", "telemetry"]
        
        for section in required_sections:
            if section not in self._config:
                logger.error(f"Missing required section: {section}")
                return False
        
        # Validate memory settings
        memory = self._config.get("memory", {})
        if memory.get("short_term", {}).get("max_size", 0) <= 0:
            logger.error("Invalid short_term.max_size")
            return False
        
        return True


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file.
    
    Args:
        path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    manager = ConfigManager(path)
    return manager.to_dict()