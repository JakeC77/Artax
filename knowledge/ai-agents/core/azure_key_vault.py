"""Azure Key Vault integration for secure key management."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for retrieved secrets
_secret_cache: dict[str, str] = {}


def get_azure_openai_api_key() -> Optional[str]:
    """Get Azure OpenAI API key from Key Vault or environment variable.
    
    Priority:
    1. Environment variable AZURE_OPENAI_API_KEY (if set)
    2. Azure Key Vault (if AZURE_KEY_VAULT_URL is configured)
    3. None (will use managed identity if available)
    
    Returns:
        API key string or None if not available
    """
    # Import here to avoid circular imports
    from app.config import Config
    
    # First, check environment variable
    if Config.AZURE_OPENAI_API_KEY:
        return Config.AZURE_OPENAI_API_KEY
    
    # If Key Vault is configured, try to retrieve from there
    if Config.AZURE_KEY_VAULT_URL:
        try:
            return get_secret_from_key_vault(Config.AZURE_KEY_VAULT_SECRET_NAME)
        except Exception as e:
            logger.warning(
                f"Failed to retrieve secret from Key Vault: {e}. "
                "Will attempt to use managed identity authentication."
            )
    
    # Return None - pydantic_ai will attempt to use managed identity
    return None


def get_secret_from_key_vault(secret_name: str) -> str:
    """Retrieve a secret from Azure Key Vault.
    
    Uses DefaultAzureCredential which supports:
    - Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, etc.)
    - Managed Identity (when running on Azure)
    - Azure CLI authentication (for local development)
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value as string
        
    Raises:
        ImportError: If azure-keyvault-secrets is not installed
        Exception: If secret retrieval fails
    """
    # Import here to avoid circular imports
    from app.config import Config
    
    # Check cache first
    cache_key = f"{Config.AZURE_KEY_VAULT_URL}:{secret_name}"
    if cache_key in _secret_cache:
        return _secret_cache[cache_key]
    
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        raise ImportError(
            "azure-keyvault-secrets and azure-identity packages are required. "
            "Install with: pip install azure-keyvault-secrets azure-identity"
        )
    
    try:
        # Create credential (supports managed identity, environment variables, Azure CLI)
        credential = DefaultAzureCredential()
        
        # Create Key Vault client
        client = SecretClient(
            vault_url=Config.AZURE_KEY_VAULT_URL,
            credential=credential
        )
        
        # Retrieve secret
        logger.info(f"Retrieving secret '{secret_name}' from Key Vault...")
        secret = client.get_secret(secret_name)
        
        # Cache the secret
        _secret_cache[cache_key] = secret.value
        
        logger.info(f"Successfully retrieved secret '{secret_name}' from Key Vault")
        return secret.value
        
    except Exception as e:
        logger.error(f"Failed to retrieve secret '{secret_name}' from Key Vault: {e}")
        raise


def clear_secret_cache():
    """Clear the secret cache. Useful for testing or when secrets are rotated."""
    global _secret_cache
    _secret_cache.clear()
    logger.info("Secret cache cleared")


