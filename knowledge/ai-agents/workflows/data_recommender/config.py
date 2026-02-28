"""Configuration for Data Recommender Workflow.

This module provides per-workflow configuration for the data recommender/scope builder,
supporting multi-provider model selection via YAML config files.

Usage:
    from app.workflows.data_recommender.config import load_config

    config = load_config()
    model_instance = config.scope_builder_model.create()
    temperature = config.scope_builder_temperature
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.workflow_config import ModelSpec


class DataRecommenderConfig(BaseModel):
    """Configuration for data recommender workflow."""

    # Model
    scope_builder_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for scope builder agent",
    )

    # Schema filtering
    excluded_entities: list[str] = Field(
        default_factory=lambda: ["Entity", "Episodic"],
        description="Entity types to exclude from schema discovery (hidden from agent prompt)",
    )

    # Settings
    scope_builder_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for scope builder (lower = more deterministic)",
    )
    scope_builder_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of retries for scope builder",
    )


# Module-level cached config
_config: Optional[DataRecommenderConfig] = None


def load_config(config_path: Optional[str] = None) -> DataRecommenderConfig:
    """Load config from YAML file or use defaults.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.

    Returns:
        DataRecommenderConfig instance with validated settings.
    """
    global _config

    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config

    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = DataRecommenderConfig()
            return _config
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = DataRecommenderConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result

    result = DataRecommenderConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> DataRecommenderConfig:
    """Force reload of configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()


__all__ = ["DataRecommenderConfig", "load_config", "reload_config"]
