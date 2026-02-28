"""Utilities for per-workflow configuration with multi-provider model support.

This module provides ModelSpec for flexible model configuration that works with both:
- Simple string format: "openai:gpt-4o-mini" (backward compatible)
- Structured format: {provider: "azure", model: "gpt-4o"} (multi-provider capable)
- Full settings: {provider: "google", model: "gemini-2.5-pro", thinking: true}

Usage in workflow config.py files:
    from app.core.workflow_config import ModelSpec

    class MyWorkflowConfig(BaseModel):
        my_model: ModelSpec = ModelSpec(model="gpt-4o-mini")

Usage in workflow YAML files:
    # String format (simple)
    my_model: "openai:gpt-4o-mini"

    # Object format (multi-provider)
    my_model:
      provider: azure
      model: gpt-4o

    # With thinking enabled (Google Gemini)
    my_model:
      provider: google
      model: gemini-2.5-pro
      thinking: true

Usage in workflow code:
    config = load_config()
    model_instance = config.my_model.create()
    model_settings = config.my_model.get_model_settings()
    agent = Agent(model=model_instance, ...)
    agent.model_settings = model_settings
"""

from typing import Optional, Any, Dict, Literal

from pydantic import BaseModel, model_validator

from app.core.model_factory import create_model


class ModelSpec(BaseModel):
    """Flexible model specification - accepts string or object format.

    YAML examples:
        # String format (simple)
        model: "openai:gpt-4o-mini"

        # Object format (multi-provider)
        model:
          provider: azure
          model: gpt-4o

        # With model settings
        model:
          provider: google
          model: gemini-2.5-pro
          temperature: 0.4
          thinking: true
          thinking_budget: 10000

    Attributes:
        model: Model name or provider:model string
        provider: Optional provider override (azure, anthropic, google, etc.)
        temperature: Optional temperature setting (0.0 to 2.0)
        thinking: Enable thinking mode (for supported models like Gemini 2.5)
        thinking_budget: Token budget for thinking (-1 unlimited, 0 disabled)
    """

    model: str
    provider: Optional[str] = None
    temperature: Optional[float] = None
    thinking: Optional[bool] = None
    thinking_budget: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def parse_string_format(cls, data: Any) -> dict:
        """Accept string format and convert to dict.

        Allows YAML like:
            my_model: "openai:gpt-4o-mini"

        Instead of requiring:
            my_model:
              model: "openai:gpt-4o-mini"
        """
        if isinstance(data, str):
            return {"model": data, "provider": None}
        return data

    def create(self) -> Any:
        """Create model instance using model_factory.

        Returns:
            Model instance suitable for Agent(model=...).
            Returns str for simple cases, or provider-specific model objects
            (OpenAIChatModel, AnthropicModel, etc.) for complex cases.

        This method routes through the model_factory which handles:
        - Azure auto-detection and deployment mapping
        - Provider-specific model instantiation
        - Environment variable overrides
        """
        # If model contains ":", parse the provider from the string
        if ":" in self.model and self.provider is None:
            parts = self.model.split(":", 1)
            return create_model(parts[1], parts[0])

        # Use model_factory with explicit provider (or None for default)
        return create_model(self.model, self.provider)

    def get_model_settings(self, temperature_override: Optional[float] = None) -> Any:
        """Build model_settings for Agent.

        Args:
            temperature_override: Optional temperature to use instead of config value.
                                  Useful when workflows have separate temperature settings.

        Returns:
            ModelSettings or provider-specific subclass (e.g., GoogleModelSettings).
            Returns None if no settings are configured.

        Example:
            config = load_config()
            agent = Agent(model=config.my_model.create())
            agent.model_settings = config.my_model.get_model_settings()
        """
        from pydantic_ai.settings import ModelSettings

        # Temperature - use override if provided, otherwise use config value
        temp = temperature_override if temperature_override is not None else self.temperature

        # Google-specific thinking configuration
        effective_provider = self._get_effective_provider()
        if effective_provider == "google":
            # Use GoogleModelSettings for Google provider
            from pydantic_ai.models.google import GoogleModelSettings

            thinking_config: Optional[Dict[str, Any]] = None
            if self.thinking is not None or self.thinking_budget is not None:
                thinking_config = {}
                if self.thinking is True:
                    thinking_config["include_thoughts"] = True
                if self.thinking_budget is not None:
                    thinking_config["thinking_budget"] = self.thinking_budget

            # Only return settings if we have something to configure
            if temp is not None or thinking_config is not None:
                return GoogleModelSettings(
                    temperature=temp,
                    google_thinking_config=thinking_config
                )
            return None

        # Default: use base ModelSettings
        if temp is not None:
            return ModelSettings(temperature=temp)

        return None

    def _get_effective_provider(self) -> Optional[str]:
        """Determine the effective provider from model string or explicit provider."""
        if self.provider:
            return self.provider
        if ":" in self.model:
            return self.model.split(":", 1)[0]
        return None

    def __str__(self) -> str:
        """String representation for logging."""
        if self.provider:
            return f"{self.provider}:{self.model}"
        return self.model

    def __repr__(self) -> str:
        """Debug representation."""
        parts = [f"model={self.model!r}"]
        if self.provider:
            parts.insert(0, f"provider={self.provider!r}")
        if self.temperature is not None:
            parts.append(f"temperature={self.temperature}")
        if self.thinking is not None:
            parts.append(f"thinking={self.thinking}")
        if self.thinking_budget is not None:
            parts.append(f"thinking_budget={self.thinking_budget}")
        return f"ModelSpec({', '.join(parts)})"


__all__ = ["ModelSpec"]
