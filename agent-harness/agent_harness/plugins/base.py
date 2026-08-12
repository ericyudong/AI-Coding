"""
Plugin base classes for Agent Harness framework.

Provides extensibility through plugins.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Base class for all plugins.
    
    Plugins can extend agent functionality by:
    - Adding new tools
    - Modifying behavior
    - Adding telemetry
    - Custom memory handling
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
        self._enabled = True
    
    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled
    
    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False
    
    async def initialize(self) -> None:
        """Initialize the plugin."""
        pass
    
    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass
    
    @abstractmethod
    def get_hooks(self) -> Dict[str, Any]:
        """
        Get plugin hooks.
        
        Returns:
            Dictionary mapping hook names to callback functions
        """
        pass


class PluginRegistry:
    """Registry for managing plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._hooks: Dict[str, List[Any]] = {}
    
    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin."""
        self._plugins[plugin.name] = plugin
        
        # Register hooks
        for hook_name, callback in plugin.get_hooks().items():
            if hook_name not in self._hooks:
                self._hooks[hook_name] = []
            self._hooks[hook_name].append(callback)
        
        logger.info(f"Registered plugin: {plugin.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name."""
        if name in self._plugins:
            plugin = self._plugins[name]
            
            # Remove hooks
            for hook_name, callback in plugin.get_hooks().items():
                if hook_name in self._hooks and callback in self._hooks[hook_name]:
                    self._hooks[hook_name].remove(callback)
            
            del self._plugins[name]
            logger.info(f"Unregistered plugin: {name}")
            return True
        return False
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugin names."""
        return list(self._plugins.keys())
    
    async def initialize_all(self) -> None:
        """Initialize all plugins."""
        for plugin in self._plugins.values():
            if plugin.enabled:
                await plugin.initialize()
    
    async def cleanup_all(self) -> None:
        """Cleanup all plugins."""
        for plugin in self._plugins.values():
            await plugin.cleanup()
    
    async def execute_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """Execute all callbacks for a hook."""
        results = []
        for callback in self._hooks.get(hook_name, []):
            try:
                if hasattr(callback, '__call__'):
                    import asyncio
                    if asyncio.iscoroutinefunction(callback):
                        result = await callback(**kwargs)
                    else:
                        result = callback(**kwargs)
                    results.append(result)
            except Exception as e:
                logger.error(f"Error executing hook {hook_name}: {e}")
        return results