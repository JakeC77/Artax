"""
config.py - Configuration for data loading workflow
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from app.core.workflow_config import ModelSpec


class DataLoadingConfig(BaseModel):
    """Configuration for data loading workflow."""
    
    # Agent configuration
    data_loader_model: ModelSpec = Field(
        default_factory=lambda: ModelSpec(model="gpt-4o-mini"),
        description="LLM model for data loader agent"
    )
    
    data_loader_temperature: float = Field(
        default=float(os.getenv("DATA_LOADER_TEMPERATURE", "0.3")),
        description="Temperature for data loader agent"
    )
    
    data_loader_retries: int = Field(
        default=int(os.getenv("DATA_LOADER_RETRIES", "2")),
        description="Number of retries for agent operations"
    )
    
    # Performance configuration
    max_batch_size: int = Field(
        default=int(os.getenv("DATA_LOADING_MAX_BATCH_SIZE", "100")),
        description="Maximum number of nodes to create per batch"
    )
    
    # Feature flags
    enable_preview: bool = Field(
        default=os.getenv("DATA_LOADING_ENABLE_PREVIEW", "true").lower() == "true",
        description="Show preview before insertion"
    )
    
    auto_confirm_mapping: bool = Field(
        default=os.getenv("DATA_LOADING_AUTO_CONFIRM_MAPPING", "false").lower() == "true",
        description="Skip confirmation if mapping confidence is high"
    )
    
    # CSV parsing
    csv_sample_rows: int = Field(
        default=int(os.getenv("DATA_LOADING_CSV_SAMPLE_ROWS", "10")),
        description="Number of rows to sample for type detection"
    )
    
    csv_max_rows_preview: int = Field(
        default=int(os.getenv("DATA_LOADING_MAX_PREVIEW_ROWS", "5")),
        description="Maximum rows to show in preview"
    )


_config: Optional[DataLoadingConfig] = None


def load_config(config_path: Optional[str] = None) -> DataLoadingConfig:
    """Load config from YAML file or use defaults.
    
    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in the same directory.
    
    Returns:
        DataLoadingConfig instance with validated settings.
    """
    global _config
    
    # Return cached config if no custom path and already loaded
    if config_path is None and _config is not None:
        return _config
    
    import yaml
    
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
        if not config_path.exists():
            _config = DataLoadingConfig()
            return _config
    else:
        config_path = Path(config_path)
    
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            result = DataLoadingConfig(**data)
            if config_path == Path(__file__).parent / "config.yaml":
                _config = result
            return result
    
    result = DataLoadingConfig()
    if config_path is None:
        _config = result
    return result


def reload_config() -> DataLoadingConfig:
    """Reload configuration (useful for testing)."""
    global _config
    _config = None
    return load_config()
