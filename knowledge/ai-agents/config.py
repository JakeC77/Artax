"""Configuration management for Azure Container App."""

import os
import urllib.parse
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Get the directory where this config file is located
_CONFIG_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
# Try loading from config directory first, then current directory
env_file = _CONFIG_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"Loaded .env file from: {env_file}")
else:
    # Try current working directory
    from pathlib import Path as PathLib
    cwd_env = PathLib.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)
        print(f"Loaded .env file from: {cwd_env}")
    else:
        load_dotenv(override=True)  # Fallback to current directory
        print(f"No .env file found in {env_file} or {cwd_env}. Using environment variables only.")


class Config:
    """Application configuration from environment variables."""
    
    # Service Bus Configuration
    SERVICE_BUS_CONNECTION_STRING: str = os.getenv(
        "AZURE_SERVICE_BUS_CONNECTION_STRING",
        ""
    )
    SERVICE_BUS_QUEUE_NAME: str = os.getenv(
        "AZURE_SERVICE_BUS_QUEUE_NAME",
        "workflow-events"
    )
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Workflow Configuration
    # Default to workflows directory relative to config file location
    _default_workflow_dir = _CONFIG_DIR / "workflows"
    WORKFLOW_DIRECTORY: Path = Path(
        os.getenv("WORKFLOW_DIRECTORY", str(_default_workflow_dir))
    )
    # Resolve to absolute path
    if not WORKFLOW_DIRECTORY.is_absolute():
        WORKFLOW_DIRECTORY = _CONFIG_DIR / WORKFLOW_DIRECTORY
    WORKFLOW_DIRECTORY = WORKFLOW_DIRECTORY.resolve()
    
    # Application Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    HEALTH_CHECK_PORT: int = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
    
    # GraphQL API Configuration (for streaming logs/results)
    GRAPHQL_ENDPOINT: str = os.getenv(
        "WORKSPACE_GRAPHQL_ENDPOINT",
        "https://app-sbx-westus3-01.azurewebsites.net/gql/"
    )
    GRAPHQL_TIMEOUT: float = float(os.getenv("WORKSPACE_GRAPHQL_TIMEOUT", "30"))
    GRAPHQL_LOGGING_ENABLED: bool = os.getenv(
        "GRAPHQL_LOGGING_ENABLED",
        "true"
    ).lower() == "true"
    
    # GraphQL Authentication Configuration (Entra External IDs)
    GRAPHQL_AUTH_ENABLED: bool = os.getenv(
        "GRAPHQL_AUTH_ENABLED",
        "true"
    ).lower() == "true"
    GRAPHQL_AUTH_SCOPE: Optional[str] = os.getenv("GRAPHQL_AUTH_SCOPE")
    
    # Client Secret Authentication (alternative to managed identity)
    GRAPHQL_AUTH_CLIENT_ID: Optional[str] = os.getenv("GRAPHQL_AUTH_CLIENT_ID")
    GRAPHQL_AUTH_CLIENT_SECRET: Optional[str] = os.getenv("GRAPHQL_AUTH_CLIENT_SECRET")
    GRAPHQL_AUTH_TENANT_ID: Optional[str] = os.getenv("GRAPHQL_AUTH_TENANT_ID")
    
    # Workflow Execution Configuration
    MAX_WORKFLOW_DURATION_SECONDS: int = int(
        os.getenv("MAX_WORKFLOW_DURATION_SECONDS", "600")  # 10 minutes default
    )
    MAX_CONCURRENT_MESSAGES: int = int(
        os.getenv("MAX_CONCURRENT_MESSAGES", "100")  # Increased for scalability
    )
    
    # Conversation Management Configuration
    MAX_CONVERSATION_DURATION_SECONDS: int = int(
        os.getenv("MAX_CONVERSATION_DURATION_SECONDS", "3600")  # 1 hour default
    )
    CONVERSATION_IDLE_TIMEOUT_SECONDS: int = int(
        os.getenv("CONVERSATION_IDLE_TIMEOUT_SECONDS", "1200")  # 20 minutes default
    )
    # Ontology conversation: save a summary on session end for resume (experimental)
    ONTOLOGY_CONVERSATION_SAVE_SUMMARY: bool = os.getenv(
        "ONTOLOGY_CONVERSATION_SAVE_SUMMARY", "false"
    ).lower() == "true"

    # HTTP Connection Configuration
    MAX_HTTP_CONNECTIONS: int = int(
        os.getenv("MAX_HTTP_CONNECTIONS", "200")  # Max concurrent HTTP connections
    )
    
    # Retry Configuration
    MAX_RETRY_ATTEMPTS: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    RETRY_BACKOFF_SECONDS: int = int(os.getenv("RETRY_BACKOFF_SECONDS", "5"))
    
    # Service Bus Lock Configuration
    SERVICE_BUS_MAX_LOCK_DURATION_SECONDS: int = int(
        os.getenv("SERVICE_BUS_MAX_LOCK_DURATION_SECONDS", "300")  # 5 minutes default
    )
    SERVICE_BUS_LOCK_RENEWAL_INTERVAL_SECONDS: int = int(
        os.getenv("SERVICE_BUS_LOCK_RENEWAL_INTERVAL_SECONDS", "60")  # Renew every 60 seconds
    )

    # Logfire Observability Configuration
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "sandbox")  # sandbox | development | production
    LOGFIRE_ENABLED: bool = os.getenv("LOGFIRE_ENABLED", "true").lower() == "true"
    LOGFIRE_TOKEN: Optional[str] = os.getenv("LOGFIRE_TOKEN")  # Optional - uses .logfire/ if not set
    LOGFIRE_PROJECT_NAME: str = os.getenv("LOGFIRE_PROJECT_NAME", "geodesicai")
    LOGFIRE_SERVICE_NAME: str = os.getenv("LOGFIRE_SERVICE_NAME", "workspace")
    
    # Azure Key Vault Configuration (optional)
    AZURE_KEY_VAULT_URL: Optional[str] = os.getenv("AZURE_KEY_VAULT_URL")
    AZURE_KEY_VAULT_SECRET_NAME: str = os.getenv("AZURE_KEY_VAULT_SECRET_NAME", "OpenAI-API-Key")
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")

    # Azure Blob Storage (for document workflows)
    AZURE_STORAGE_CONNECTION_STRING: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    DOCUMENT_RAW_CONTAINER: str = os.getenv("DOCUMENT_RAW_CONTAINER", "documents-raw")
    DOCUMENT_PROCESSED_CONTAINER: str = os.getenv("DOCUMENT_PROCESSED_CONTAINER", "documents-processed")

    # Document workflow configuration
    DOCUMENT_INDEXING_TIMEOUT: float = float(os.getenv("DOCUMENT_INDEXING_TIMEOUT", "60"))
    DOCUMENT_INDEXING_CHUNK_MAX_CHARS: int = int(
        os.getenv("DOCUMENT_INDEXING_CHUNK_MAX_CHARS", "6000")
    )
    DOCUMENT_INDEXING_LLM_MODEL: Optional[str] = os.getenv("DOCUMENT_INDEXING_LLM_MODEL")
    ENTITY_RESOLUTION_MODEL: Optional[str] = os.getenv("ENTITY_RESOLUTION_MODEL")
    ENTITY_RESOLUTION_PROVIDER: str = os.getenv("ENTITY_RESOLUTION_PROVIDER", "google")
    ENTITY_RESOLUTION_MAX_TOOL_CALLS: int = int(
        os.getenv("ENTITY_RESOLUTION_MAX_TOOL_CALLS", "30")
    )
    ENTITY_RESOLUTION_PHASE2_ENABLED: bool = os.getenv(
        "ENTITY_RESOLUTION_PHASE2_ENABLED", "false"
    ).lower() == "true"

    # Graphiti / Neo4j (document-graphiti workflow)
    GRAPHITI_ENABLED: bool = os.getenv("GRAPHITI_ENABLED", "false").lower() == "true"
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    # Neo4j encryption key for per-ontology password decryption (32-byte base64-encoded key)
    NEO4J_ENCRYPTION_KEY_BASE64: Optional[str] = os.getenv("NEO4J__ENCRYPTIONKEYBASE64")
    # Graphiti LLM: use Gemini when GOOGLE_API_KEY (or GEMINI_API_KEY) is set; else OpenAI
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    GRAPHITI_GEMINI_MODEL: str = os.getenv("GRAPHITI_GEMINI_MODEL", "gemini-2.0-flash")
    GRAPHITI_GEMINI_EMBEDDING_MODEL: str = os.getenv(
        "GRAPHITI_GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
    )
    GRAPHITI_GEMINI_RERANKER_MODEL: str = os.getenv(
        "GRAPHITI_GEMINI_RERANKER_MODEL", "gemini-2.0-flash-exp"
    )

    # Job mode: when true, process runs as a Container Apps Job (one workflow per run, no Service Bus)
    RUN_AS_JOB: bool = os.getenv("RUN_AS_JOB", "false").lower() == "true"

    # Python execution (isolated run for workflows; see docs/python-execution-azure-design.md)
    PYTHON_EXECUTION_ENABLED: bool = os.getenv(
        "PYTHON_EXECUTION_ENABLED", "false"
    ).lower() == "true"
    PYTHON_RUNNER_URL: Optional[str] = os.getenv("PYTHON_RUNNER_URL")
    PYTHON_EXECUTION_DEFAULT_TIMEOUT: int = int(
        os.getenv("PYTHON_EXECUTION_DEFAULT_TIMEOUT", "30")
    )
    PYTHON_EXECUTION_MAX_TIMEOUT: int = int(
        os.getenv("PYTHON_EXECUTION_MAX_TIMEOUT", "300")
    )
    PYTHON_EXECUTION_MAX_MEMORY_MB: int = int(
        os.getenv("PYTHON_EXECUTION_MAX_MEMORY_MB", "1024")
    )
    PYTHON_EXECUTION_MAX_CODE_LENGTH: int = int(
        os.getenv("PYTHON_EXECUTION_MAX_CODE_LENGTH", "50000")
    )
    PYTHON_EXECUTION_MAX_INPUTS_BYTES: int = int(
        os.getenv("PYTHON_EXECUTION_MAX_INPUTS_BYTES", "5242880")
    )  # 5 MB

    @classmethod
    def is_azure_configured(cls) -> bool:
        """Check if Azure OpenAI is configured.
        
        Returns:
            True if both endpoint and deployment name are set
        """
        return bool(cls.AZURE_OPENAI_ENDPOINT and cls.AZURE_OPENAI_DEPLOYMENT_NAME)
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration and return list of missing items."""
        missing = []

        # Service Bus not required when running as a Container Apps Job (payload via env/URL)
        if not cls.RUN_AS_JOB and not cls.SERVICE_BUS_CONNECTION_STRING:
            missing.append("AZURE_SERVICE_BUS_CONNECTION_STRING")
        
        # Validate OpenAI/Azure OpenAI configuration
        # Either Azure OpenAI (endpoint + deployment) OR OpenAI API key must be configured
        is_azure = cls.is_azure_configured()
        has_openai_key = bool(cls.OPENAI_API_KEY)
        
        if not is_azure and not has_openai_key:
            missing.append("Either Azure OpenAI (AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_DEPLOYMENT_NAME) or OPENAI_API_KEY must be configured")
        
        # If Azure is configured, validate required fields
        if is_azure:
            if not cls.AZURE_OPENAI_ENDPOINT:
                missing.append("AZURE_OPENAI_ENDPOINT (required for Azure OpenAI)")
            if not cls.AZURE_OPENAI_DEPLOYMENT_NAME:
                missing.append("AZURE_OPENAI_DEPLOYMENT_NAME (required for Azure OpenAI)")
        
        # Validate GraphQL auth scope if authentication is enabled
        if cls.GRAPHQL_AUTH_ENABLED and not cls.GRAPHQL_AUTH_SCOPE:
            missing.append("GRAPHQL_AUTH_SCOPE (required when GRAPHQL_AUTH_ENABLED=true)")
        
        # Validate client secret auth - if any client secret field is set, all must be set
        has_client_id = bool(cls.GRAPHQL_AUTH_CLIENT_ID)
        has_client_secret = bool(cls.GRAPHQL_AUTH_CLIENT_SECRET)
        has_tenant_id = bool(cls.GRAPHQL_AUTH_TENANT_ID)
        
        if has_client_id or has_client_secret or has_tenant_id:
            if not has_client_id:
                missing.append("GRAPHQL_AUTH_CLIENT_ID (required when using client secret authentication)")
            if not has_client_secret:
                missing.append("GRAPHQL_AUTH_CLIENT_SECRET (required when using client secret authentication)")
            if not has_tenant_id:
                missing.append("GRAPHQL_AUTH_TENANT_ID (required when using client secret authentication)")
        
        # Workflow directory doesn't need to exist at startup (workflows registered programmatically)
        # But we'll check if it's a valid path
        if not cls.WORKFLOW_DIRECTORY.parent.exists():
            missing.append(f"WORKFLOW_DIRECTORY (parent path does not exist: {cls.WORKFLOW_DIRECTORY.parent})")
        
        return missing
    
    @classmethod
    def get_summary(cls) -> dict:
        """Get configuration summary (without secrets)."""
        summary = {
            "service_bus_queue": cls.SERVICE_BUS_QUEUE_NAME,
            "workflow_directory": str(cls.WORKFLOW_DIRECTORY),
            "log_level": cls.LOG_LEVEL,
            "health_check_port": cls.HEALTH_CHECK_PORT,
            "max_concurrent_messages": cls.MAX_CONCURRENT_MESSAGES,
            "max_workflow_duration_seconds": cls.MAX_WORKFLOW_DURATION_SECONDS,
            "max_conversation_duration_seconds": cls.MAX_CONVERSATION_DURATION_SECONDS,
            "conversation_idle_timeout_seconds": cls.CONVERSATION_IDLE_TIMEOUT_SECONDS,
            "max_http_connections": cls.MAX_HTTP_CONNECTIONS,
            "graphql_logging_enabled": cls.GRAPHQL_LOGGING_ENABLED,
            "graphql_endpoint": cls.GRAPHQL_ENDPOINT,
            "graphql_auth_enabled": cls.GRAPHQL_AUTH_ENABLED,
            "graphql_auth_scope_configured": cls.GRAPHQL_AUTH_SCOPE is not None,
            "environment": cls.ENVIRONMENT,
            "logfire_enabled": cls.LOGFIRE_ENABLED,
            "logfire_service_name": cls.LOGFIRE_SERVICE_NAME,
        }
        
        # Add GraphQL auth details (without exposing secrets)
        if cls.GRAPHQL_AUTH_CLIENT_ID and cls.GRAPHQL_AUTH_CLIENT_SECRET and cls.GRAPHQL_AUTH_TENANT_ID:
            summary["graphql_auth_method"] = "client_secret"
            summary["graphql_auth_client_id"] = cls.GRAPHQL_AUTH_CLIENT_ID[:8] + "..." if len(cls.GRAPHQL_AUTH_CLIENT_ID) > 8 else "***"
            summary["graphql_auth_tenant_id"] = cls.GRAPHQL_AUTH_TENANT_ID
            summary["graphql_auth_client_secret"] = "***"  # Never show secret
        else:
            summary["graphql_auth_method"] = "managed_identity_or_default"
        
        # Add OpenAI provider info
        if cls.is_azure_configured():
            summary["openai_provider"] = "azure"
            summary["azure_openai_endpoint_configured"] = True
            summary["azure_openai_deployment"] = cls.AZURE_OPENAI_DEPLOYMENT_NAME
            summary["azure_openai_api_version"] = cls.AZURE_OPENAI_API_VERSION
        else:
            summary["openai_provider"] = "openai"
            summary["openai_api_key_configured"] = bool(cls.OPENAI_API_KEY)

        # Document workflows
        summary["document_raw_container"] = cls.DOCUMENT_RAW_CONTAINER
        summary["document_processed_container"] = cls.DOCUMENT_PROCESSED_CONTAINER
        summary["graphql_endpoint_configured"] = bool(cls.GRAPHQL_ENDPOINT)

        return summary

