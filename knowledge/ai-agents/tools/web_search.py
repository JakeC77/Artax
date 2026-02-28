"""Web search and crawl tool using Firecrawl.

Why: Enables agents to search and retrieve information from the web for external context.
Tradeoff: Adds API dependency and latency, but provides access to current information.

Use case: Agent needs to research current events, find documentation, or gather
external information that's not in its training data.

Design decisions:
- Uses Firecrawl for search + content extraction (combines search and scraping)
- Returns structured results with sources and statistics
- Graceful error handling (returns error info instead of crashing)
- Supports both search-only and search+scrape modes
- Tracks metrics: sites visited, time taken, estimated tokens

Alternative considered: DuckDuckGo/Tavily (simpler, but less powerful for content extraction)
Why Firecrawl: Better for crawling/scraping content, not just search results
"""

from __future__ import annotations

import asyncio
import os
import time
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from app.tools import register_tool

logger = logging.getLogger(__name__)

# Try to import Firecrawl, but handle gracefully if not installed
# Note: Package name is 'firecrawl-py' but import is 'firecrawl'
FIRECRAWL_AVAILABLE = False
FirecrawlApp: Any = None

try:
    from firecrawl import FirecrawlApp  # type: ignore[no-redef]
    FIRECRAWL_AVAILABLE = True
except ImportError:
    logger.warning(
        "Firecrawl not installed. Install with: pip install firecrawl-py"
    )


class SearchResult(BaseModel):
    """Individual search result with content.

    The content field contains the full page content (when scrape_content=True, default)
    or a snippet (when scrape_content=False). The snippet field always contains a
    short preview for quick reference.
    """

    title: str = Field(description="Page title")
    url: str = Field(description="Source URL for citation")
    content: str = Field(description="Full page content (markdown) or snippet, depending on scrape_content setting")
    snippet: Optional[str] = Field(
        default=None, description="Short snippet/preview from search results"
    )


class SearchStatistics(BaseModel):
    """Statistics about the search operation."""

    sites_visited: int = Field(description="Number of sites crawled/visited")
    time_taken_seconds: float = Field(description="Time taken for the search operation")
    estimated_tokens: int = Field(
        description="Estimated token count of retrieved content"
    )


class WebSearchResponse(BaseModel):
    """Structured response from web search tool."""

    results: list[SearchResult] = Field(description="List of search results with content")
    sources: list[str] = Field(description="List of source URLs")
    statistics: SearchStatistics = Field(description="Search operation statistics")
    error: Optional[str] = Field(
        default=None, description="Error message if search failed"
    )


def _estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token)."""
    return len(text) // 4


DEFAULT_TIMEOUT_SECONDS = 30


def _search_firecrawl(
    query: str,
    max_results: int = 5,
    scrape_content: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Synchronous Firecrawl search implementation.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        scrape_content: If True, scrape full content from pages
        timeout_seconds: Timeout for the Firecrawl API call (default: 30s)

    Returns:
        Dictionary with search results, sources, statistics, and optional error
    """
    start_time = time.time()

    # Check if Firecrawl is available
    if not FIRECRAWL_AVAILABLE:
        error_msg = (
            "Firecrawl not installed. Install with: pip install firecrawl-py. "
            "Also set FIRECRAWL_API_KEY environment variable."
        )
        logger.error(error_msg)
        return {
            "results": [],
            "sources": [],
            "statistics": {
                "sites_visited": 0,
                "time_taken_seconds": 0.0,
                "estimated_tokens": 0,
            },
            "error": error_msg,
        }

    # Get API key from environment
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        error_msg = (
            "FIRECRAWL_API_KEY environment variable not set. "
            "Get an API key from https://www.firecrawl.dev/"
        )
        logger.error(error_msg)
        return {
            "results": [],
            "sources": [],
            "statistics": {
                "sites_visited": 0,
                "time_taken_seconds": 0.0,
                "estimated_tokens": 0,
            },
            "error": error_msg,
        }

    # Validate max_results
    if max_results < 1:
        max_results = 1
    elif max_results > 20:
        max_results = 20
        logger.warning(f"max_results capped at 20 (requested: {max_results})")

    try:
        # Initialize Firecrawl client with timeout
        app = FirecrawlApp(api_key=api_key)

        # Perform search
        logger.info(
            f"Performing web search: query='{query}', max_results={max_results}, "
            f"scrape_content={scrape_content}, timeout={timeout_seconds}s",
            extra={"query": query, "max_results": max_results, "timeout": timeout_seconds}
        )

        if scrape_content:
            # Search with content scraping
            response = app.search(
                query=query,
                limit=max_results,
                scrape_options={"formats": ["markdown"]},
                timeout=timeout_seconds
            )
        else:
            # Search only (no scraping)
            response = app.search(
                query=query,
                limit=max_results,
                timeout=timeout_seconds
            )

        # Debug: Log the raw response structure
        logger.debug(
            f"Firecrawl raw response type: {type(response)}",
            extra={"response_type": str(type(response))}
        )

        # Parse response
        # Firecrawl v2 returns a SearchData object with a .web attribute
        web_results = []

        # Check if response is a SearchData object (has .web attribute)
        if hasattr(response, 'web'):
            web_results = response.web if response.web else []
            logger.debug(
                f"Found {len(web_results)} results in response.web",
                extra={"first_result_type": type(web_results[0]).__name__ if web_results else None}
            )
        elif isinstance(response, dict):
            # Try multiple possible dict structures
            if "data" in response:
                data = response["data"]
                if isinstance(data, dict):
                    web_results = data.get("web", [])
                    if not web_results:
                        for key in ["results", "items", "searchResults"]:
                            if key in data:
                                web_results = data[key]
                                break
                elif isinstance(data, list):
                    web_results = data
            else:
                for key in ["web", "results", "items", "searchResults"]:
                    if key in response:
                        web_results = response[key]
                        break
        elif isinstance(response, list):
            web_results = response

        logger.debug(
            f"Parsed web_results: {len(web_results)} items",
            extra={"results_count": len(web_results)}
        )

        if not web_results:
            logger.warning(
                f"No results found in Firecrawl response. Response type: {type(response)}",
                extra={
                    "has_web_attr": hasattr(response, 'web') if response else False,
                    "response_keys": list(response.keys()) if isinstance(response, dict) else None
                }
            )

        # Build results
        search_results: list[SearchResult] = []
        sources: list[str] = []

        for item in web_results:
            # Handle both dict and object (SearchResultWeb) formats
            item_dict: dict[str, Any] = {}

            if isinstance(item, dict):
                item_dict = item
            elif hasattr(item, 'model_dump') and callable(getattr(item, 'model_dump')):
                item_dict = item.model_dump()  # type: ignore[union-attr]
            elif hasattr(item, '__dict__'):
                item_dict = dict(vars(item))
                for attr in ['url', 'title', 'description', 'snippet', 'markdown', 'content']:
                    if hasattr(item, attr) and attr not in item_dict:
                        item_dict[attr] = getattr(item, attr, None)
            else:
                for attr in ['url', 'title', 'description', 'snippet', 'markdown', 'content']:
                    try:
                        if hasattr(item, attr):
                            item_dict[attr] = getattr(item, attr, None)
                    except Exception:
                        pass

            # Extract metadata first - Firecrawl puts title/url there
            metadata = item_dict.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            # Extract title - try direct field first, then metadata
            title = item_dict.get("title")
            if not title or title == "Untitled":
                title = (
                    metadata.get("title")
                    or metadata.get("ogTitle")
                    or metadata.get("og:title")
                    or "Untitled"
                )

            # Extract URL - try direct field first, then metadata
            url = item_dict.get("url")
            if not url:
                url = (
                    metadata.get("url")
                    or metadata.get("sourceURL")
                    or metadata.get("ogUrl")
                    or metadata.get("og:url")
                    or ""
                )

            # Extract content (markdown if scraped, otherwise snippet/description)
            content = ""
            if scrape_content:
                content = item_dict.get("markdown") or item_dict.get("content") or item_dict.get("description") or ""
            else:
                content = item_dict.get("snippet") or item_dict.get("description") or ""

            # Get snippet for preview
            snippet = item_dict.get("snippet") or item_dict.get("description") or content[:200]

            if not title or title == "Untitled":
                logger.debug(
                    f"Missing title in search result. Keys: {list(item_dict.keys())}, metadata: {metadata}",
                    extra={"item_type": type(item).__name__, "metadata": metadata}
                )
            if not url:
                logger.debug(
                    f"Missing URL in search result. Keys: {list(item_dict.keys())}, metadata: {metadata}",
                    extra={"item_type": type(item).__name__, "metadata": metadata}
                )

            search_results.append(
                SearchResult(
                    title=title,
                    url=url,
                    content=content,
                    snippet=snippet[:500] if snippet else None,
                )
            )
            sources.append(url)

        # Calculate statistics
        time_taken = time.time() - start_time
        estimated_tokens = _estimate_tokens(
            " ".join([r.content for r in search_results])
        )

        statistics = SearchStatistics(
            sites_visited=len(search_results),
            time_taken_seconds=round(time_taken, 2),
            estimated_tokens=estimated_tokens,
        )

        logger.info(
            f"Web search completed: {len(search_results)} results, "
            f"{time_taken:.2f}s, ~{estimated_tokens} tokens",
            extra={
                "query": query,
                "results_count": len(search_results),
                "time_taken": time_taken,
                "estimated_tokens": estimated_tokens,
            }
        )

        return {
            "results": [r.model_dump() for r in search_results],
            "sources": sources,
            "statistics": statistics.model_dump(),
        }

    except Exception as e:
        error_str = str(e)
        if "Rate Limit" in error_str or "rate limit" in error_str.lower():
            error_msg = f"Rate limit exceeded: {error_str}"
            logger.warning(
                error_msg,
                extra={"query": query, "max_results": max_results, "error_type": "rate_limit"},
            )
        else:
            error_msg = f"Web search failed: {error_str}"
            logger.error(
                error_msg,
                extra={"query": query, "max_results": max_results},
                exc_info=True
            )

        time_taken = time.time() - start_time
        return {
            "results": [],
            "sources": [],
            "statistics": {
                "sites_visited": 0,
                "time_taken_seconds": round(time_taken, 2),
                "estimated_tokens": 0,
            },
            "error": error_msg,
        }


@register_tool("web_search")
async def web_search(
    ctx: RunContext[dict],
    query: str,
    max_results: int = 5,
    scrape_content: bool = True,
) -> dict[str, Any]:
    """Search the web and scrape content from results using Firecrawl.

    Why: Agents need access to current web information for research, fact-checking,
    and gathering external context. This tool provides search results with full
    page content that agents can use to extract relevant information.

    IMPORTANT: By default, this tool scrapes full page content (scrape_content=True)
    to provide agents with actual information, not just titles. The agent can then
    extract and summarize the relevant parts. Set scrape_content=False only if you
    need faster results with minimal content.

    This tool performs a web search using Firecrawl and scrapes content from results.
    Use it when:
    - You need current information not in training data
    - You need to research a topic with external sources
    - You need to verify facts or find documentation
    - You need detailed information from web pages, not just titles

    Example queries:
    - "latest developments in quantum computing 2024"
    - "Python async/await best practices"
    - "current weather in San Francisco"
    - "GLP-1 drug market analysis 2024"

    Args:
        ctx: Pydantic AI context (passed automatically)
        query: Search query string
        max_results: Maximum number of results to return (default: 5, max: 20)
        scrape_content: If True, scrape full content from pages (default: True).
                       If False, return only search snippets (faster but minimal info).

    Returns:
        Dictionary with:
        - results: List of SearchResult objects (title, url, content, snippet)
        - sources: List of source URLs for citations
        - statistics: SearchStatistics (sites_visited, time_taken_seconds, estimated_tokens)
        - error: Optional error message if search failed
        - budget_remaining: Number of web_search calls remaining (if budget enabled)

    Examples:
        >>> # Basic search with full content (default - provides actual information)
        >>> result = await web_search(ctx, query="Python async best practices", max_results=3)
        >>> # Returns full page content that agents can extract information from

        >>> # Search with snippets only (faster but minimal information)
        >>> result = await web_search(ctx, query="quick lookup", scrape_content=False)

    Note:
        - Requires FIRECRAWL_API_KEY environment variable
        - Get an API key from https://www.firecrawl.dev/
        - Rate limits may apply based on your Firecrawl plan
        - Budget limits may apply per agent phase (check budget_remaining in response)
    """
    # Budget tracking
    budget_max_calls = ctx.deps.get("web_search_budget_max_calls") if ctx.deps else None
    budget_state = ctx.deps.get("web_search_budget_state") if ctx.deps else None

    # Initialize state on first call if budget configured but state not yet created
    if budget_max_calls is not None and budget_state is None:
        budget_state = {"calls_made": 0, "queries": []}
        ctx.deps["web_search_budget_state"] = budget_state

    # Check call budget before executing
    if budget_state is not None and budget_max_calls is not None:
        if budget_state["calls_made"] >= budget_max_calls:
            logger.warning(
                f"Web search budget exhausted: {budget_state['calls_made']}/{budget_max_calls} calls used"
            )
            return {
                "results": [],
                "sources": [],
                "statistics": {
                    "sites_visited": 0,
                    "time_taken_seconds": 0.0,
                    "estimated_tokens": 0,
                },
                "error": f"Web search budget exhausted ({budget_max_calls} calls). No more searches allowed in this phase.",
                "budget_remaining": 0,
            }

    # Run the synchronous Firecrawl search in a thread pool to avoid blocking
    # Use asyncio.wait_for as a fallback timeout in case Firecrawl SDK doesn't honor its timeout
    timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _search_firecrawl,
                query,
                max_results,
                scrape_content,
                timeout_seconds
            ),
            timeout=timeout_seconds + 5  # Give Firecrawl SDK 5s grace period before hard cutoff
        )
    except asyncio.TimeoutError:
        logger.error(
            f"Web search timed out after {timeout_seconds + 5}s (hard cutoff): query='{query}'",
            extra={"query": query, "timeout": timeout_seconds + 5}
        )
        result = {
            "results": [],
            "sources": [],
            "statistics": {
                "sites_visited": 0,
                "time_taken_seconds": timeout_seconds + 5,
                "estimated_tokens": 0,
            },
            "error": f"Web search timed out after {timeout_seconds + 5} seconds",
        }

    # Update budget state after successful call
    if budget_state is not None:
        budget_state["calls_made"] += 1
        budget_state["queries"].append({
            "query": query,
            "results_count": len(result.get("results", [])),
            "error": result.get("error"),
        })
        remaining = budget_max_calls - budget_state["calls_made"] if budget_max_calls else None
        result["budget_remaining"] = remaining
        logger.info(
            f"Web search budget: {budget_state['calls_made']}/{budget_max_calls} calls, "
            f"{remaining} remaining"
        )

    return result


__all__ = ["web_search", "WebSearchResponse", "SearchResult", "SearchStatistics"]
