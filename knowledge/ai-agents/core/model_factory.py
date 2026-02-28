"""Model factory for creating pydantic-ai models with multi-provider support.

This module provides a centralized way to create models for various providers:
- OpenAI (gpt-4o, gpt-4o-mini, o1, etc.)
- Azure OpenAI (uses deployment names)
- Anthropic (claude-sonnet-4-5, claude-opus-4, etc.)
- Google Gemini (gemini-2.5-pro, gemini-2.5-flash)
- Groq (llama-3.3-70b, mixtral)
- Mistral (mistral-large, mistral-small)
- Ollama (local models)
- AWS Bedrock
- And more via OpenAI-compatible APIs

Configuration is loaded from app/models.yaml via model_config.
"""

import logging
from typing import Union, Optional

from app.config import Config
from app.core.azure_key_vault import get_azure_openai_api_key

logger = logging.getLogger(__name__)


def create_model(
    model_name: str = "gpt-4o",
    provider: Optional[str] = None
) -> Union[str, object]:
    """Create a pydantic-ai model for any supported provider.

    This function routes to the appropriate provider-specific factory based on
    configuration. Provider detection order:
    1. Explicit provider argument
    2. Component-specific provider from model_config (if using create_model_for_component)
    3. Azure auto-detection via Config.is_azure_configured()
    4. default_provider from models.yaml
    5. OpenAI fallback

    Args:
        model_name: Model name (e.g., "gpt-4o", "claude-sonnet-4-5", "gemini-2.5-pro")
        provider: Provider override. If None, auto-detects from config.

    Returns:
        Model instance appropriate for the provider

    Supported providers:
        - openai: OpenAI API
        - azure: Azure OpenAI (auto-detected if configured)
        - anthropic: Anthropic API
        - google: Google Gemini
        - groq: Groq
        - mistral: Mistral AI
        - ollama: Local Ollama
        - bedrock: AWS Bedrock
        - together: Together AI
        - fireworks: Fireworks AI
        - deepseek: DeepSeek
        - openrouter: OpenRouter

    Example:
        >>> model = create_model("gpt-4o")
        >>> agent = Agent(model=model)

        >>> model = create_model("claude-sonnet-4-5", provider="anthropic")
        >>> agent = Agent(model=model)
    """
    from app.core.model_config import model_config

    # Determine effective provider
    effective_provider = provider

    if effective_provider is None:
        # Check Azure auto-detection first (backward compatibility)
        if Config.is_azure_configured():
            effective_provider = "azure"
        else:
            effective_provider = model_config.default_provider

    # Route to provider-specific factory
    if effective_provider == "azure":
        return _create_azure_model(model_name)
    elif effective_provider == "anthropic":
        return _create_anthropic_model(model_name)
    elif effective_provider == "google":
        return _create_google_model(model_name)
    elif effective_provider == "groq":
        return _create_groq_model(model_name)
    elif effective_provider == "mistral":
        return _create_mistral_model(model_name)
    elif effective_provider == "ollama":
        return _create_ollama_model(model_name)
    elif effective_provider == "bedrock":
        return _create_bedrock_model(model_name)
    elif effective_provider == "together":
        return _create_together_model(model_name)
    elif effective_provider == "fireworks":
        return _create_fireworks_model(model_name)
    elif effective_provider == "deepseek":
        return _create_deepseek_model(model_name)
    elif effective_provider == "openrouter":
        return _create_openrouter_model(model_name)
    else:
        # Default to OpenAI
        return f"openai:{model_name}"


def create_model_for_component(component: str) -> Union[str, object]:
    """Create a model for a named component using central config.

    Looks up the component in models.yaml and creates the appropriate model
    with the configured settings.

    Args:
        component: Component name (e.g., "theo", "conductor", "chat_conductor")

    Returns:
        Model instance configured for the component

    Example:
        >>> model = create_model_for_component("theo")
        >>> # Returns model configured per models.yaml theo section
    """
    from app.core.model_config import model_config

    config = model_config.get(component)
    return create_model(config.model, config.provider)


def _create_azure_model(model_name: str = "gpt-4o") -> object:
    """Create an Azure OpenAI model instance.

    Uses deployment mapping from models.yaml if available, otherwise
    falls back to Config.AZURE_OPENAI_DEPLOYMENT_NAME.

    Args:
        model_name: Model name to map to deployment

    Returns:
        OpenAIChatModel instance configured for Azure OpenAI
    """
    from app.core.model_config import model_config

    try:
        from pydantic_ai.models.openai import OpenAIChatModel

        # Get deployment name from config mapping or use model_name
        deployment_name = model_config.get_azure_deployment(model_name)

        # If no mapping found and we have a global deployment, use that
        if deployment_name == model_name and Config.AZURE_OPENAI_DEPLOYMENT_NAME:
            deployment_name = Config.AZURE_OPENAI_DEPLOYMENT_NAME

        # Try to use AzureProvider if available (newer pydantic-ai versions)
        try:
            from pydantic_ai.providers.azure import AzureProvider

            # Get API key (from env var or Key Vault, or None for managed identity)
            api_key = get_azure_openai_api_key()

            # Create Azure provider
            provider = AzureProvider(
                azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                api_version=Config.AZURE_OPENAI_API_VERSION,
                api_key=api_key,  # None is OK - will use managed identity
            )

            # Create model with deployment name
            model = OpenAIChatModel(
                deployment_name,
                provider=provider,
            )

            logger.info(
                "Created Azure OpenAI model using AzureProvider",
                extra={
                    "deployment": deployment_name,
                    "requested_model": model_name,
                    "endpoint": Config.AZURE_OPENAI_ENDPOINT,
                    "api_version": Config.AZURE_OPENAI_API_VERSION,
                    "auth_method": "api_key" if api_key else "managed_identity",
                }
            )

            return model

        except ImportError:
            # AzureProvider not available, fall back to OpenAIProvider with base_url
            from pydantic_ai.providers.openai import OpenAIProvider

            # Get API key (from env var or Key Vault, or None for managed identity)
            api_key = get_azure_openai_api_key()

            if not api_key:
                logger.warning(
                    "Azure OpenAI API key not found. Managed identity authentication "
                    "may not work with OpenAIProvider. Consider upgrading pydantic-ai "
                    "to use AzureProvider for managed identity support."
                )

            # For Azure, we need to construct the base URL properly
            endpoint = Config.AZURE_OPENAI_ENDPOINT.rstrip('/')
            base_url = f"{endpoint}/openai/deployments/{deployment_name}"

            provider = OpenAIProvider(
                api_key=api_key,
                base_url=base_url,
            )

            model = OpenAIChatModel(
                deployment_name,
                provider=provider,
            )

            logger.info(
                "Created Azure OpenAI model using OpenAIProvider with base_url",
                extra={
                    "deployment": deployment_name,
                    "requested_model": model_name,
                    "endpoint": Config.AZURE_OPENAI_ENDPOINT,
                    "api_version": Config.AZURE_OPENAI_API_VERSION,
                    "auth_method": "api_key" if api_key else "api_key_required",
                }
            )

            return model

    except ImportError as e:
        logger.error(
            f"Failed to import pydantic-ai models: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise
    except Exception as e:
        logger.error(
            f"Failed to create Azure OpenAI model: {e}",
            exc_info=True
        )
        raise


def _create_anthropic_model(model_name: str) -> object:
    """Create an Anthropic model instance.

    Uses ANTHROPIC_API_KEY from environment.

    Args:
        model_name: Model name (e.g., "claude-sonnet-4-5", "claude-opus-4")

    Returns:
        AnthropicModel instance
    """
    try:
        from pydantic_ai.models.anthropic import AnthropicModel

        model = AnthropicModel(model_name)
        logger.info(f"Created Anthropic model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import Anthropic model: {e}. "
            "Make sure pydantic-ai[anthropic] is installed."
        )
        raise


def _create_google_model(model_name: str) -> object:
    """Create a Google Gemini model instance.

    Uses GOOGLE_API_KEY from environment or gcloud authentication.

    Args:
        model_name: Model name (e.g., "gemini-2.5-pro", "gemini-2.5-flash")

    Returns:
        GoogleModel instance
    """
    try:
        from pydantic_ai.models.google import GoogleModel

        model = GoogleModel(model_name)
        logger.info(f"Created Google Gemini model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import Google model: {e}. "
            "Make sure pydantic-ai[google] is installed."
        )
        raise


def _create_groq_model(model_name: str) -> object:
    """Create a Groq model instance.

    Uses GROQ_API_KEY from environment.

    Args:
        model_name: Model name (e.g., "llama-3.3-70b", "mixtral-8x7b")

    Returns:
        GroqModel instance
    """
    try:
        from pydantic_ai.models.groq import GroqModel

        model = GroqModel(model_name)
        logger.info(f"Created Groq model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import Groq model: {e}. "
            "Make sure pydantic-ai[groq] is installed."
        )
        raise


def _create_mistral_model(model_name: str) -> object:
    """Create a Mistral model instance.

    Uses MISTRAL_API_KEY from environment.

    Args:
        model_name: Model name (e.g., "mistral-large", "mistral-small")

    Returns:
        MistralModel instance
    """
    try:
        from pydantic_ai.models.mistral import MistralModel

        model = MistralModel(model_name)
        logger.info(f"Created Mistral model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import Mistral model: {e}. "
            "Make sure pydantic-ai[mistral] is installed."
        )
        raise


def _create_ollama_model(model_name: str) -> object:
    """Create a local Ollama model instance.

    Uses OLLAMA_HOST from environment or defaults to localhost.
    Ollama provides an OpenAI-compatible API.

    Args:
        model_name: Model name (e.g., "llama3.2", "mistral", "codellama")

    Returns:
        OpenAIChatModel configured for Ollama
    """
    from app.core.model_config import model_config

    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        host = model_config.get_provider_setting(
            "ollama", "host", "http://localhost:11434"
        )

        provider = OpenAIProvider(
            base_url=f"{host}/v1",
            api_key="ollama",  # Ollama doesn't require a real key
        )

        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Created Ollama model: {model_name} at {host}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import OpenAI models for Ollama: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise


def _create_bedrock_model(model_name: str) -> object:
    """Create an AWS Bedrock model instance.

    Uses AWS credentials from environment (boto3 default credential chain).

    Args:
        model_name: Model name (e.g., "anthropic.claude-v2", "amazon.titan")

    Returns:
        BedrockModel instance
    """
    try:
        from pydantic_ai.models.bedrock import BedrockModel

        model = BedrockModel(model_name)
        logger.info(f"Created AWS Bedrock model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import Bedrock model: {e}. "
            "Make sure pydantic-ai[bedrock] is installed."
        )
        raise


def _create_together_model(model_name: str) -> object:
    """Create a Together AI model instance.

    Uses TOGETHER_API_KEY from environment.
    Together AI provides an OpenAI-compatible API.

    Args:
        model_name: Model name (e.g., "meta-llama/Llama-3-70b")

    Returns:
        OpenAIChatModel configured for Together AI
    """
    import os

    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("TOGETHER_API_KEY environment variable not set")

        provider = OpenAIProvider(
            base_url="https://api.together.xyz/v1",
            api_key=api_key,
        )

        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Created Together AI model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import OpenAI models for Together: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise


def _create_fireworks_model(model_name: str) -> object:
    """Create a Fireworks AI model instance.

    Uses FIREWORKS_API_KEY from environment.
    Fireworks AI provides an OpenAI-compatible API.

    Args:
        model_name: Model name (e.g., "accounts/fireworks/models/llama-v3")

    Returns:
        OpenAIChatModel configured for Fireworks AI
    """
    import os

    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.getenv("FIREWORKS_API_KEY")
        if not api_key:
            raise ValueError("FIREWORKS_API_KEY environment variable not set")

        provider = OpenAIProvider(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=api_key,
        )

        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Created Fireworks AI model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import OpenAI models for Fireworks: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise


def _create_deepseek_model(model_name: str) -> object:
    """Create a DeepSeek model instance.

    Uses DEEPSEEK_API_KEY from environment.
    DeepSeek provides an OpenAI-compatible API.

    Args:
        model_name: Model name (e.g., "deepseek-chat", "deepseek-coder")

    Returns:
        OpenAIChatModel configured for DeepSeek
    """
    import os

    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        provider = OpenAIProvider(
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
        )

        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Created DeepSeek model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import OpenAI models for DeepSeek: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise


def _create_openrouter_model(model_name: str) -> object:
    """Create an OpenRouter model instance.

    Uses OPENROUTER_API_KEY from environment.
    OpenRouter provides access to multiple providers through a single API.

    Args:
        model_name: Model name (e.g., "openai/gpt-4o", "anthropic/claude-3")

    Returns:
        OpenAIChatModel configured for OpenRouter
    """
    import os

    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        model = OpenAIChatModel(model_name, provider=provider)
        logger.info(f"Created OpenRouter model: {model_name}")
        return model

    except ImportError as e:
        logger.error(
            f"Failed to import OpenAI models for OpenRouter: {e}. "
            "Make sure pydantic-ai is installed."
        )
        raise


def get_model_string(model_name: str = "gpt-4o") -> str:
    """Get a model string representation.

    This is a convenience function that returns the model string format
    for cases where a string is needed (e.g., logging, configuration).

    Args:
        model_name: Base model name

    Returns:
        Model string in format "openai:{model_name}" or "azure:{deployment}"
    """
    from app.core.model_config import model_config

    if Config.is_azure_configured():
        deployment = model_config.get_azure_deployment(model_name)
        return f"azure:{deployment}"
    else:
        return f"openai:{model_name}"


__all__ = [
    "create_model",
    "create_model_for_component",
    "get_model_string",
]
