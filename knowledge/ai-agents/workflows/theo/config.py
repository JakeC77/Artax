"""Configuration for Theo Workflow.

This module provides per-workflow configuration for Theo agents,
supporting multi-provider model selection via YAML config files.

Usage:
    from app.workflows.theo.config import load_config

    config = load_config()
    model_instance = config.theo_model.create()
    temperature = config.theo_temperature
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.workflow_config import ModelSpec


class TheoWorkflowConfig(BaseModel):
    """Configuration for Theo workflow agents."""

    # Models
    theo_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for main Theo conversational agent",
    )
    intent_builder_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o"),
        description="Model for intent builder orchestration",
    )
    team_builder_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o"),
        description="Model for team builder",
    )

    # Temperature settings
    theo_temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
        description="Temperature for Theo agent",
    )
    intent_builder_temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
        description="Temperature for intent builder",
    )
    team_builder_temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
        description="Temperature for team builder",
    )

    # Retry settings
    theo_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of retries for Theo agent",
    )
    intent_builder_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of retries for intent builder",
    )
    team_builder_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of retries for team builder",
    )


# Module-level cached config
_config: Optional[TheoWorkflowConfig] = None


def load_config(config_path: Optional[str] = None) -> TheoWorkflowConfig:
    """Load config from YAML file or use defaults.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.

    Returns:
        TheoWorkflowConfig instance with validated settings.
    """
    global _config

    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config

    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = TheoWorkflowConfig()
            return _config
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = TheoWorkflowConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result

    result = TheoWorkflowConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> TheoWorkflowConfig:
    """Force reload of configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()


__all__ = ["TheoWorkflowConfig", "load_config", "reload_config"]
