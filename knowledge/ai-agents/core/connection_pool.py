"""Connection pool for managing HTTP client connections."""

import asyncio
import logging
from typing import Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Manages a pool of HTTP clients with connection limits."""
    
    def __init__(self, max_connections: int = 200, timeout: float = 30.0):
        """Initialize connection pool.
        
        Args:
            max_connections: Maximum number of concurrent connections
            timeout: Default timeout for connections
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx package not installed. "
                "Install with: pip install httpx"
            )
        
        self.max_connections = max_connections
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_connections)
        self._active_connections = 0
        self._lock = asyncio.Lock()
    
    async def get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """Get an HTTP client from the pool.
        
        Args:
            timeout: Optional timeout override
            
        Returns:
            httpx.AsyncClient instance
            
        Note:
            Caller is responsible for closing the client when done.
            Use as a context manager: async with pool.get_client() as client:
        """
        await self._semaphore.acquire()
        
        async with self._lock:
            self._active_connections += 1
        
        try:
            client = httpx.AsyncClient(timeout=timeout or self.timeout)
            logger.debug(
                f"Created HTTP client. Active connections: {self._active_connections}/{self.max_connections}"
            )
            return client
        except Exception as e:
            async with self._lock:
                self._active_connections -= 1
            self._semaphore.release()
            raise
    
    async def release_client(self, client: httpx.AsyncClient):
        """Release a client back to the pool.
        
        Args:
            client: Client to release
        """
        try:
            await client.aclose()
        except Exception as e:
            logger.warning(f"Error closing HTTP client: {e}")
        finally:
            async with self._lock:
                self._active_connections = max(0, self._active_connections - 1)
            self._semaphore.release()
            logger.debug(
                f"Released HTTP client. Active connections: {self._active_connections}/{self.max_connections}"
            )
    
    def get_active_connections(self) -> int:
        """Get current number of active connections."""
        return self._active_connections
    
    def get_available_slots(self) -> int:
        """Get number of available connection slots."""
        return self.max_connections - self._active_connections


# Global connection pool instance
_global_pool: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _global_pool
    if _global_pool is None:
        from app.config import Config
        _global_pool = ConnectionPool(
            max_connections=Config.MAX_HTTP_CONNECTIONS,
            timeout=Config.GRAPHQL_TIMEOUT
        )
    return _global_pool


