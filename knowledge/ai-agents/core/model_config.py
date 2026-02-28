"""Model configuration loader with typed access and environment variable overrides.

This module provides centralized model configuration management through:
1. YAML file (app/models.yaml) for base configuration
2. Environment variable overrides for deployment flexibility
3. Pydantic validation for type safety
4. Singleton caching for performance

Usage:
    from app.core.model_config import model_config

    # Get full configuration for a component
    config = model_config.get("theo")
    model_name = config.model
    temperature = config.temperature

    # Shorthand accessors
    model_name = model_config.model("theo")
    temperature = model_config.temperature("theo")

    # Get default provider
    provider = model_config.default_provider

    # Get provider-specific settings
    host = model_config.get_provider_setting("ollama", "host", "http://localhost:11434")
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ComponentConfig(BaseModel):
    """Configuration for a single component."""
    model: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    retries: int = Field(default=2, ge=0, le=10)
    timeout: int = Field(default=60, ge=1)
    provider: Optional[str] = Field(default=None)  # None = use default_provider


class ProviderConfig(BaseModel):
    """Configuration for a provider."""
    enabled: bool = Field(default=False)
    # Additional provider-specific settings stored as dict
    settings: Dict[str, Any] = Field(default_factory=dict)


class ModelConfigSchema(BaseModel):
    """Schema for the entire models.yaml file."""
    default_provider: str = Field(default="openai")
    providers: Dict[str, Any] = Field(default_factory=dict)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    components: Dict[str, Any] = Field(default_factory=dict)
    aliases: Dict[str, str] = Field(default_factory=dict)


class ModelConfigLoader:
    """Singleton loader for model configuration with env var overrides.

    Configuration resolution order (highest to lowest priority):
    1. Environment variable (MODEL_<COMPONENT>_<SETTING>)
    2. Component-specific config in YAML
    3. Defaults section in YAML
    4. Hardcoded fallbacks
    """

    _instance: Optional['ModelConfigLoader'] = None
    _config: Optional[ModelConfigSchema] = None
    _config_path: Optional[Path] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._load_config()
            self._initialized = True

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        # Find config file relative to this module (app/core/model_config.py -> app/models.yaml)
        self._config_path = Path(__file__).parent.parent / "models.yaml"

        if not self._config_path.exists():
            logger.warning(
                f"Model config file not found at {self._config_path}. "
                "Using default configuration."
            )
            self._config = ModelConfigSchema()
            return

        try:
            import yaml
            with open(self._config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}

            self._config = ModelConfigSchema(**raw_config)
            logger.info(f"Loaded model configuration from {self._config_path}")

        except ImportError:
            logger.error(
                "PyYAML not installed. Install with: pip install pyyaml. "
                "Using default configuration."
            )
            self._config = ModelConfigSchema()
        except Exception as e:
            logger.error(f"Error loading model config: {e}. Using defaults.")
            self._config = ModelConfigSchema()

    def reload(self) -> None:
        """Force reload of configuration (useful for testing)."""
        self._initialized = False
        self._config = None
        self._load_config()
        self._initialized = True

    @property
    def default_provider(self) -> str:
        """Get the default provider, with env var override."""
        env_provider = os.getenv("MODEL_DEFAULT_PROVIDER")
        if env_provider:
            return env_provider
        return self._config.default_provider

    def _resolve_alias(self, model_name: str) -> str:
        """Resolve model alias to actual model name."""
        return self._config.aliases.get(model_name, model_name)

    def _get_env_override(self, component: str, setting: str) -> Optional[str]:
        """Check for environment variable override.

        Format: MODEL_<COMPONENT>_<SETTING> (e.g., MODEL_THEO_MODEL)
        """
        env_key = f"MODEL_{component.upper()}_{setting.upper()}"
        return os.getenv(env_key)

    def get(self, component: str) -> ComponentConfig:
        """Get configuration for a component with env var overrides.

        Resolution order:
        1. Environment variable (MODEL_<COMPONENT>_<SETTING>)
        2. Component-specific config in YAML
        3. Defaults section in YAML
        4. Pydantic model defaults

        Args:
            component: Component name (e.g., "theo", "conductor")

        Returns:
            ComponentConfig with merged settings
        """
        # Start with Pydantic defaults
        merged = {
            "model": "gpt-4o",
            "temperature": 0.7,
            "retries": 2,
            "timeout": 60,
            "provider": None,
        }

        # Merge YAML defaults
        if self._config.defaults:
            for key in merged:
                if key in self._config.defaults:
                    merged[key] = self._config.defaults[key]

        # Merge component-specific config
        component_config = self._config.components.get(component, {})
        if component_config:
            for key, value in component_config.items():
                if value is not None and key in merged:
                    merged[key] = value

        # Apply environment variable overrides
        for setting in ['model', 'temperature', 'retries', 'timeout', 'provider']:
            env_value = self._get_env_override(component, setting)
            if env_value is not None:
                if setting == 'temperature':
                    merged[setting] = float(env_value)
                elif setting in ('retries', 'timeout'):
                    merged[setting] = int(env_value)
                else:
                    merged[setting] = env_value

        # Resolve model alias
        merged['model'] = self._resolve_alias(merged['model'])

        return ComponentConfig(**merged)

    def model(self, component: str) -> str:
        """Shorthand to get model name for a component."""
        return self.get(component).model

    def temperature(self, component: str) -> float:
        """Shorthand to get temperature for a component."""
        return self.get(component).temperature

    def retries(self, component: str) -> int:
        """Shorthand to get retries for a component."""
        return self.get(component).retries

    def provider(self, component: str) -> Optional[str]:
        """Get provider for a component (None means use default)."""
        return self.get(component).provider

    def get_provider_setting(
        self,
        provider_name: str,
        setting: str,
        default: Any = None
    ) -> Any:
        """Get a provider-specific setting.

        Args:
            provider_name: Provider name (e.g., "ollama", "azure")
            setting: Setting name (e.g., "host", "deployments")
            default: Default value if not found

        Returns:
            Setting value or default
        """
        provider_config = self._config.providers.get(provider_name, {})
        if isinstance(provider_config, dict):
            return provider_config.get(setting, default)
        return default

    def is_provider_enabled(self, provider_name: str) -> bool:
        """Check if a provider is enabled in config."""
        provider_config = self._config.providers.get(provider_name, {})
        if isinstance(provider_config, dict):
            return provider_config.get("enabled", False)
        return False

    def get_azure_deployment(self, model_name: str) -> str:
        """Get Azure deployment name for a model.

        Uses the deployments mapping in providers.azure.deployments,
        falling back to the model name itself if no mapping exists.
        """
        deployments = self.get_provider_setting("azure", "deployments", {})
        return deployments.get(model_name, model_name)


# Module-level singleton instance
model_config = ModelConfigLoader()


__all__ = ["model_config", "ModelConfigLoader", "ComponentConfig"]
