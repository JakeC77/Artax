"""Configuration for Ontology Creation Workflow.

This module provides per-workflow configuration for ontology creation agents,
supporting multi-provider model selection via YAML config files.

Usage:
    from app.workflows.ontology_creation.config import load_config

    config = load_config()
    model_instance = config.ontology_agent_model.create()
    temperature = config.ontology_agent_temperature
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.workflow_config import ModelSpec


class OntologyCreationWorkflowConfig(BaseModel):
    """Configuration for ontology creation workflow agents."""

    # Models
    ontology_agent_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="Model for ontology creation conversational agent",
    )

    # Temperature settings
    ontology_agent_temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
        description="Temperature for ontology agent",
    )

    # Retry settings
    ontology_agent_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of retries for ontology agent",
    )


# Module-level cached config
_config: Optional[OntologyCreationWorkflowConfig] = None


def load_config(config_path: Optional[str] = None) -> OntologyCreationWorkflowConfig:
    """Load config from YAML file or use defaults.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.

    Returns:
        OntologyCreationWorkflowConfig instance with validated settings.
    """
    global _config

    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config

    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = OntologyCreationWorkflowConfig()
            return _config
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = OntologyCreationWorkflowConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result

    result = OntologyCreationWorkflowConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> OntologyCreationWorkflowConfig:
    """Force reload of configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()


__all__ = ["OntologyCreationWorkflowConfig", "load_config", "reload_config"]
