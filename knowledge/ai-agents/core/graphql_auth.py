"""GraphQL API authentication using Entra External IDs with Managed Identity or Client Secret."""

import logging
import time
from typing import Optional

from app.config import Config

logger = logging.getLogger(__name__)

# Token cache with expiration tracking
_token_cache: Optional[dict] = None


def _get_token_cache() -> dict:
    """Get or initialize the token cache."""
    global _token_cache
    if _token_cache is None:
        _token_cache = {
            "token": None,
            "expires_at": 0,
            "scope": None,
        }
    return _token_cache


def get_auth_token(scope: str, force_refresh: bool = False) -> Optional[str]:
    """Get OAuth 2.0 Bearer token for GraphQL API authentication.
    
    Tries multiple authentication methods in order:
    1. ClientSecretCredential (if client ID/secret/tenant provided)
    2. DefaultAzureCredential (tries multiple sources including Azure CLI, environment variables, etc.)
    
    Note: ManagedIdentityCredential is disabled to prevent IMDS endpoint hangs in local development.
    
    Tokens are cached and automatically refreshed before expiration.
    
    Args:
        scope: The scope/audience for the token (e.g., 'api://<app-id>/GraphQL.ReadWrite')
        force_refresh: If True, force a new token even if cached token is valid
        
    Returns:
        Bearer token string (without 'Bearer ' prefix) or None if authentication fails
        
    Raises:
        ImportError: If azure-identity is not installed
    """
    try:
        from azure.identity import (
            ClientSecretCredential,
            DefaultAzureCredential,
            ManagedIdentityCredential,
        )
    except ImportError:
        raise ImportError(
            "azure-identity package is required for GraphQL authentication. "
            "Install with: pip install azure-identity"
        )
    
    cache = _get_token_cache()
    current_time = time.time()
    
    # Check if we have a valid cached token
    if not force_refresh and cache["token"] and cache["scope"] == scope:
        # Refresh if token expires within 5 minutes
        if cache["expires_at"] > current_time + 300:
            logger.debug("Using cached authentication token")
            return cache["token"]
        else:
            logger.debug("Cached token expiring soon, refreshing...")
    
    # Try authentication methods in order
    token_response = None
    credential_type = None
    
    # 1. ManagedIdentityCredential disabled to prevent IMDS endpoint hangs
    # (Commented out - causes hangs when IMDS endpoint is not available)
    # try:
    #     credential = ManagedIdentityCredential()
    #     logger.debug("Trying ManagedIdentityCredential for authentication")
    #     token_response = credential.get_token(scope)
    #     credential_type = "ManagedIdentityCredential"
    #     logger.debug("Successfully used ManagedIdentityCredential")
    # except Exception as e:
    #     logger.debug(f"ManagedIdentityCredential unavailable ({type(e).__name__}): {e}")
    
    # 2. Try ClientSecretCredential if credentials are provided
    if not token_response and Config.GRAPHQL_AUTH_CLIENT_ID and Config.GRAPHQL_AUTH_CLIENT_SECRET and Config.GRAPHQL_AUTH_TENANT_ID:
        try:
            # For Entra External IDs (CIAM), use the CIAM authority URL
            # Format: https://{tenant-id}.ciamlogin.com (library handles the rest)
            ciam_authority = f"https://{Config.GRAPHQL_AUTH_TENANT_ID}.ciamlogin.com"
            
            credential = ClientSecretCredential(
                tenant_id=Config.GRAPHQL_AUTH_TENANT_ID,
                client_id=Config.GRAPHQL_AUTH_CLIENT_ID,
                client_secret=Config.GRAPHQL_AUTH_CLIENT_SECRET,
                authority=ciam_authority,
            )
            logger.debug(f"Trying ClientSecretCredential for authentication with CIAM authority: {ciam_authority}")
            
            # Client credential flows require scope to end with /.default
            client_secret_scope = scope
            if not client_secret_scope.endswith("/.default"):
                client_secret_scope = f"{scope}/.default"
                logger.debug(f"Appending /.default to scope for client credential flow: {client_secret_scope}")
            
            token_response = credential.get_token(client_secret_scope)
            credential_type = "ClientSecretCredential"
            logger.debug("Successfully used ClientSecretCredential")
        except Exception as e:
            logger.debug(f"ClientSecretCredential failed ({type(e).__name__}): {e}")
    
    # 3. Fall back to DefaultAzureCredential (tries multiple sources)
    # But exclude Azure CLI if we have client secret credentials configured
    # to avoid tenant confusion
    if not token_response:
        try:
            # If client secret is configured, exclude Azure CLI to avoid wrong tenant
            exclude_cli = bool(Config.GRAPHQL_AUTH_CLIENT_ID and Config.GRAPHQL_AUTH_CLIENT_SECRET and Config.GRAPHQL_AUTH_TENANT_ID)
            
            if exclude_cli:
                # Create DefaultAzureCredential excluding Azure CLI
                credential = DefaultAzureCredential(exclude_cli_credential=True, exclude_managed_identity_credential=True)
                logger.debug("Trying DefaultAzureCredential (excluding Azure CLI) for authentication")
            else:
                credential = DefaultAzureCredential(exclude_managed_identity_credential=True)
                logger.debug("Trying DefaultAzureCredential for authentication")
            
            token_response = credential.get_token(scope)
            credential_type = "DefaultAzureCredential"
            logger.debug("Successfully used DefaultAzureCredential")
        except Exception as e:
            logger.error(f"All authentication methods failed. Last error: {e}")
            # Clear cache on error
            cache["token"] = None
            cache["expires_at"] = 0
            cache["scope"] = None
            return None
    
    # Cache the token (tokens typically expire in 1 hour, but we'll use expires_on if available)
    expires_at = token_response.expires_on if hasattr(token_response, 'expires_on') else current_time + 3600
    cache["token"] = token_response.token
    cache["expires_at"] = expires_at
    cache["scope"] = scope
    
    logger.info(f"Successfully acquired authentication token using {credential_type}")
    return token_response.token


def clear_token_cache():
    """Clear the token cache. Useful for testing or when tokens need to be refreshed."""
    global _token_cache
    _token_cache = None
    logger.info("Authentication token cache cleared")

