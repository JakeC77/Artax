"""Configuration for Document Indexing Workflow.

This module provides per-workflow configuration for document indexing workflows,
supporting multi-provider model selection via YAML config files.

Usage:
    from app.workflows.document_indexing.config import load_config

    config = load_config()
    model_instance = config.entity_resolution_model.create()
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.workflow_config import ModelSpec


class DocumentIndexingConfig(BaseModel):
    """Configuration for document indexing workflows."""

    # Model selection - using ModelSpec for multi-provider support
    entity_resolution_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gemini-2.5-flash", provider="google"),
        description="Model for entity resolution agent",
    )
    assertion_mining_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gemini-2.5-flash", provider="google"),
        description="Model for assertion mining agent",
    )
    entity_resolution_phase2_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gemini-2.5-flash", provider="google"),
        description="Model for entity resolution phase 2 agent (resolving assertions to domain graph)",
    )

    # Agent settings
    entity_resolution_max_tool_calls: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum tool calls per entity resolution agent run",
    )
    entity_resolution_phase2_enabled: bool = Field(
        default=False,
        description="Enable phase 2 entity resolution (resolving assertions to domain graph)",
    )

    # Workflow settings
    chunk_max_chars: int = Field(
        default=6000,
        ge=1000,
        le=20000,
        description="Maximum characters per chunk when chunking spans for Graphiti",
    )
    document_indexing_timeout: float = Field(
        default=60.0,
        ge=1.0,
        description="Timeout in seconds for document indexing API calls",
    )
    semaphore_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum concurrent Graphiti add_episode operations",
    )


# Module-level cached config
_config: Optional[DocumentIndexingConfig] = None


def load_config(config_path: Optional[str] = None) -> DocumentIndexingConfig:
    """Load config from YAML file or use defaults.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.

    Returns:
        DocumentIndexingConfig instance with validated settings.
    """
    global _config

    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config

    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = DocumentIndexingConfig()
            return _config
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = DocumentIndexingConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result

    result = DocumentIndexingConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> DocumentIndexingConfig:
    """Force reload of configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()


__all__ = ["DocumentIndexingConfig", "load_config", "reload_config"]
