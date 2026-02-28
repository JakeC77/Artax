"""Event stream reader for GraphQL Server-Sent Events."""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional, Dict, Any
from urllib.parse import urlencode

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class EventStreamReader:
    """Reads events from GraphQL event stream endpoint using Server-Sent Events."""
    
    def __init__(
        self,
        run_id: str,
        tenant_id: str,
        graphql_endpoint: str,
        timeout: float = 30.0,
    ):
        """Initialize event stream reader.
        
        Args:
            run_id: Run ID for the event stream
            tenant_id: Tenant ID for authentication
            graphql_endpoint: Base GraphQL endpoint URL
            timeout: Connection timeout in seconds
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx package not installed. "
                "Install with: pip install httpx"
            )
        
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.graphql_endpoint = graphql_endpoint.rstrip('/')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._running = False
        self._using_pool = False
        self._processed_event_ids: set[str] = set()  # Track processed event IDs to avoid duplicates
    
    def _build_event_stream_url(self) -> str:
        """Build the event stream URL.
        
        Returns:
            Full URL for the event stream endpoint
        """
        # Extract base URL from GraphQL endpoint
        # GraphQL endpoint is typically: https://domain.com/gql/
        # Event stream is at: https://domain.com/runs/{runId}/events?tid={tenantId}
        base_url = self.graphql_endpoint.replace('/gql/', '').replace('/gql', '')
        # Ensure base_url doesn't have trailing slash
        base_url = base_url.rstrip('/')
        params = urlencode({"tid": self.tenant_id})
        url = f"{base_url}/runs/{self.run_id}/events?{params}"
        logger.info(f"Built event stream URL: {url} (from GraphQL endpoint: {self.graphql_endpoint})")
        return url
    
    async def start(self):
        """Start the event stream connection."""
        if self._running:
            logger.warning("Event stream already running")
            return
        
        # Use connection pool if available, otherwise create standalone client
        try:
            from app.core.connection_pool import get_connection_pool
            pool = get_connection_pool()
            self._client = await pool.get_client(timeout=self.timeout)
            self._using_pool = True
        except ImportError:
            # Fallback to standalone client if pool not available
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._using_pool = False
        
        self._running = True
        logger.info(f"Event stream reader started for run_id={self.run_id}")
    
    async def stop(self):
        """Stop the event stream connection."""
        if not self._running:
            return
        
        self._running = False
        if self._client:
            # Release back to pool if using pool, otherwise just close
            if getattr(self, '_using_pool', False):
                try:
                    from app.core.connection_pool import get_connection_pool
                    pool = get_connection_pool()
                    await pool.release_client(self._client)
                except Exception as e:
                    logger.warning(f"Error releasing client to pool: {e}")
                    try:
                        await self._client.aclose()
                    except Exception:
                        pass
            else:
                await self._client.aclose()
            self._client = None
        logger.info(f"Event stream reader stopped for run_id={self.run_id}")
    
    def _parse_json_events(self, text: str) -> list[Dict[str, Any]]:
        """Parse JSON events from SSE text.

        Args:
            text: Raw text from SSE event

        Returns:
            List of parsed JSON event dictionaries
        """
        events = []

        # Strip whitespace (including trailing \n) before parsing
        text = text.strip()

        # Also strip any trailing newlines that might be escaped or literal
        # The graphql_logger adds "\n" to content which can cause parsing issues
        while text.endswith('\\n') or text.endswith('\n'):
            if text.endswith('\\n'):
                text = text[:-2]
            else:
                text = text[:-1]
        text = text.strip()

        # Try to parse as single JSON object first
        # Don't pre-process escapes - let json.loads handle them natively
        try:
            event = json.loads(text)
            if isinstance(event, dict) and event.get("event_type"):
                logger.info(f"Successfully parsed single JSON event: type={event.get('event_type')}")
                events.append(event)
                return events
            else:
                logger.warning(f"Parsed JSON but no event_type field. Keys: {list(event.keys()) if isinstance(event, dict) else type(event)}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse as single JSON: {e}. Text length={len(text)}, last 20 chars repr: {repr(text[-20:]) if len(text) > 20 else repr(text)}")
        
        # Try to parse concatenated JSON objects using incremental decoding.
        # Simple newline splitting breaks when JSON values contain \n characters
        # (e.g. agent_message with ".\n\nHere's the refined scope:\n\n").
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(text):
            # Skip whitespace between JSON objects
            while pos < len(text) and text[pos] in ' \t\n\r':
                pos += 1
            if pos >= len(text):
                break

            try:
                event, end_pos = decoder.raw_decode(text, pos)
                pos = end_pos
                if isinstance(event, dict) and event.get("event_type"):
                    events.append(event)
            except json.JSONDecodeError:
                # Skip past this character and try again
                pos += 1

        if not events:
            logger.warning(f"Could not parse any JSON events from text (length={len(text)})")

        return events
    
    async def read_events(
        self,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Read events from the stream.
        
        Args:
            event_types: Optional list of event types to filter for.
                        If None, yields all events.
        
        Yields:
            Event dictionaries with event_type, message, metadata, etc.
        """
        if not self._running:
            raise RuntimeError("Event stream not started. Call start() first.")
        
        url = self._build_event_stream_url()
        logger.info(f"Connecting to event stream: {url}")
        logger.info(f"Filtering for event types: {event_types if event_types else 'all'}")
        
        # Build headers with authentication
        headers = {
            "Accept": "text/event-stream",
            "X-Tenant-Id": self.tenant_id,
        }
        
        # Add authentication header if enabled
        try:
            from app.core.authenticated_graphql_client import _get_auth_header
            auth_header = _get_auth_header()
            if auth_header:
                headers["Authorization"] = auth_header
                logger.debug("Added Authorization header to event stream request")
        except Exception as e:
            logger.debug(f"Could not add authentication header to event stream: {e}")
        
        try:
            async with self._client.stream("GET", url, headers=headers) as response:
                logger.info(f"Event stream connection established. Status: {response.status_code}")
                response.raise_for_status()
                logger.info("Waiting for events from stream...")
                
                buffer = ""
                chunk_count = 0
                async for chunk in response.aiter_text():
                    if not self._running:
                        logger.info("Event stream reader stopped, breaking loop")
                        break
                    
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(f"Received first chunk from event stream (length: {len(chunk)})")
                    elif chunk_count % 10 == 0:
                        logger.debug(f"Received {chunk_count} chunks from event stream")
                    if len(chunk) > 10:
                        logger.info(f"Received chunk from event stream ({chunk})")
                    buffer += chunk
                    
                    # Process complete SSE messages (separated by \n\n)
                    while "\n\n" in buffer:
                        message, buffer = buffer.split("\n\n", 1)
                        logger.debug(f"Processing SSE message: {message[:200]}...")
                        
                        # Parse SSE format - messages can have multiple fields:
                        # id: 12042
                        # event: message
                        # data: {"event_type":"user_message","message":"hi"}
                        # Extract the event ID and data field from the message
                        event_id = None
                        data = None
                        for line in message.split('\n'):
                            line = line.strip()
                            if line.startswith("id: "):
                                event_id = line[4:].strip()  # Remove "id: " prefix and whitespace
                                logger.debug(f"Found event ID: {event_id}")
                            elif line.startswith("data: "):
                                data = line[6:].strip()  # Remove "data: " prefix and whitespace
                                logger.debug(f"Found data field: {data[:200]}...")
                        
                        # Skip if we've already processed this event ID
                        if event_id and event_id in self._processed_event_ids:
                            logger.debug(f"Skipping already processed event ID: {event_id}")
                            continue
                        
                        if data:
                            logger.info(f"Found data field, length={len(data)}, first 300 chars: {data[:300]}")

                            # Parse JSON events
                            events = self._parse_json_events(data)
                            logger.info(f"Parsed {len(events)} events from data")
                            
                            for event in events:
                                event_type = event.get("event_type")
                                logger.info(f"Received event: type={event_type}, id={event_id}, filtering={event_types is not None}")
                                
                                # Filter by event type if specified
                                if event_types is None or event_type in event_types:
                                    # Mark this event ID as processed
                                    if event_id:
                                        self._processed_event_ids.add(event_id)
                                        logger.debug(f"Marked event ID {event_id} as processed")
                                    
                                    logger.info(f"Yielding event: {event_type} (id: {event_id})")
                                    yield event
                                else:
                                    logger.debug(f"Filtered out event type {event_type} (not in {event_types})")
                        else:
                            # No data field found - might be a keep-alive or other SSE message
                            logger.debug(f"SSE message has no data field: {message[:100]}...")
                
                logger.info(f"Event stream ended after {chunk_count} chunks")
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error reading event stream: {e}")
            logger.error(f"URL was: {url}")
            raise
        except Exception as e:
            logger.exception(f"Error reading event stream: {e}")
            logger.error(f"URL was: {url}")
            raise
    
    async def wait_for_event(
        self,
        event_type: str | list[str],
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Wait for a specific event type or one of multiple event types.
        
        Args:
            event_type: Event type(s) to wait for (string or list of strings)
            timeout: Optional timeout in seconds
        
        Returns:
            Event dictionary or None if timeout
        """
        try:
            # Normalize to list
            if isinstance(event_type, str):
                event_types = [event_type]
            else:
                event_types = event_type
            
            if timeout is not None:
                # Use asyncio.wait_for to wrap the async generator
                async def get_first_event():
                    async for event in self.read_events(event_types=event_types):
                        return event
                    return None
                
                return await asyncio.wait_for(get_first_event(), timeout=timeout)
            else:
                async for event in self.read_events(event_types=event_types):
                    return event
                return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for event type(s): {event_types}")
            return None
        except Exception as e:
            logger.exception(f"Error waiting for event: {e}")
            return None

