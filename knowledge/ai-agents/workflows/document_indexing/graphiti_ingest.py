"""Graphiti ingestion: add document spans/chunks as episodes to a knowledge graph."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.config import Config
from app.workflows.document_indexing.config import load_config

if TYPE_CHECKING:
    from app.workflows.document_indexing.models import Span  # noqa: F401

logger = logging.getLogger(__name__)

# Lazy Graphiti client; None if disabled or import failed
_graphiti_client: Optional[object] = None
_indices_built: bool = False

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType

    _GRAPHITI_AVAILABLE = True
except ImportError:
    Graphiti = None  # type: ignore[misc, assignment]
    EpisodeType = None  # type: ignore[misc, assignment]
    _GRAPHITI_AVAILABLE = False


def _is_graphiti_configured() -> bool:
    """Return True if Graphiti is enabled and Neo4j credentials are set."""
    if not Config.GRAPHITI_ENABLED:
        return False
    if not _GRAPHITI_AVAILABLE:
        return False
    if not Config.NEO4J_URI or not Config.NEO4J_USER:
        return False
    if not Config.NEO4J_PASSWORD:
        logger.warning("Graphiti enabled but NEO4J_PASSWORD is empty")
        return False
    return True


def _build_graphiti_with_gemini():  # noqa: ANN202
    """Build Graphiti with Gemini LLM/embedder/reranker when GOOGLE_API_KEY is set."""
    if not Config.GOOGLE_API_KEY:
        return None
    try:
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.gemini_client import GeminiClient
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
    except ImportError as e:
        logger.debug("Graphiti Gemini not available (install graphiti-core[google-genai]): %s", e)
        return None
    api_key = Config.GOOGLE_API_KEY
    llm_config = LLMConfig(api_key=api_key, model=Config.GRAPHITI_GEMINI_MODEL)
    embedder_config = GeminiEmbedderConfig(
        api_key=api_key, embedding_model=Config.GRAPHITI_GEMINI_EMBEDDING_MODEL
    )
    reranker_config = LLMConfig(api_key=api_key, model=Config.GRAPHITI_GEMINI_RERANKER_MODEL)
    return Graphiti(
        Config.NEO4J_URI,
        Config.NEO4J_USER,
        Config.NEO4J_PASSWORD,
        llm_client=GeminiClient(config=llm_config),
        embedder=GeminiEmbedder(config=embedder_config),
        cross_encoder=GeminiRerankerClient(config=reranker_config),
    )


async def ensure_graphiti_client() -> Optional[object]:
    """
    Return a configured Graphiti client, or None if disabled/misconfigured.

    Uses Gemini when GOOGLE_API_KEY (or GEMINI_API_KEY) is set and
    graphiti-core[google-genai] is installed; otherwise uses OpenAI (OPENAI_API_KEY).
    Builds indices and constraints on first successful connection.
    """
    global _graphiti_client, _indices_built
    if _graphiti_client is not None:
        return _graphiti_client
    if not _is_graphiti_configured():
        return None
    try:
        client = _build_graphiti_with_gemini()
        if client is None:
            client = Graphiti(
                Config.NEO4J_URI,
                Config.NEO4J_USER,
                Config.NEO4J_PASSWORD,
            )
            logger.debug("Graphiti using default LLM (OpenAI)")
        else:
            logger.info("Graphiti using Gemini for LLM/embedder/reranker")
        if not _indices_built:
            await client.build_indices_and_constraints()
            _indices_built = True
        _graphiti_client = client
        return client
    except Exception as e:
        logger.warning("Failed to create Graphiti client: %s", e)
        return None


def _group_id(tenant_id: str) -> str:
    """Namespace for tenant; use tenant_id or prefixed form."""
    if not tenant_id:
        return "default"
    if tenant_id.startswith("tenant_"):
        return tenant_id
    return f"tenant_{tenant_id}"


async def ingest_document_into_graphiti(
    tenant_id: str,
    doc_id: str,
    spans: list[Span],
    *,
    use_chunks: bool = True,
    max_chars_per_chunk: Optional[int] = None,
) -> int:
    """
    Ingest document text into Graphiti as episodes (one per chunk or per span).

    Uses group_id for tenant isolation. Episode names include doc_id for provenance.

    Args:
        tenant_id: Tenant identifier (used as group_id namespace).
        doc_id: Document identifier (included in episode names).
        spans: List of spans from normalization.
        use_chunks: If True, chunk spans (via existing chunking) and add one episode
            per chunk; if False, add one episode per span.
        max_chars_per_chunk: Max characters per chunk when use_chunks=True; default
            from Config.DOCUMENT_INDEXING_CHUNK_MAX_CHARS.

    Returns:
        Number of episodes added. 0 if Graphiti is disabled, misconfigured, or
        spans are empty.
    """
    from app.workflows.document_indexing.chunking import spans_to_chunks

    if not spans:
        return 0

    client = await ensure_graphiti_client()
    if client is None:
        logger.debug("Graphiti client not available; skipping ingest")
        return 0

    group = _group_id(tenant_id or "")
    ref_time = datetime.now(timezone.utc)
    source_desc = "document chunk" if use_chunks else "document span"

    if use_chunks:
        # Use config (with fallback to environment variable for backward compatibility)
        workflow_config = load_config()
        default_max_chars = getattr(Config, "DOCUMENT_INDEXING_CHUNK_MAX_CHARS", None) or workflow_config.chunk_max_chars
        max_chars = max_chars_per_chunk or default_max_chars
        chunks = spans_to_chunks(spans, max_chars=max_chars)
        texts_and_names: list[tuple[str, str]] = []
        for i, ch in enumerate(chunks):
            text = (ch.text or "").strip()
            if not text:
                continue
            name = f"doc_{doc_id}_chunk_{i}"
            texts_and_names.append((text, name))
    else:
        texts_and_names = []
        for i, sp in enumerate(spans):
            text = (sp.text or "").strip()
            if not text:
                continue
            name = f"doc_{doc_id}_span_{i}_{(sp.span_id or '')[:8]}"
            texts_and_names.append((text, name))

    # Use config semaphore limit (with fallback to environment variable for backward compatibility)
    workflow_config = load_config()
    semaphore_limit = getattr(Config, "SEMAPHORE_LIMIT", None) or workflow_config.semaphore_limit
    semaphore = asyncio.Semaphore(semaphore_limit)

    async def add_episode_with_semaphore(text: str, name: str) -> bool:
        """Add episode with semaphore-controlled concurrency."""
        async with semaphore:
            try:
                await client.add_episode(
                    name=name,
                    episode_body=text,
                    source=EpisodeType.text,
                    source_description=source_desc,
                    reference_time=ref_time,
                    group_id=group,
                )
                return True
            except Exception as e:
                logger.warning("Graphiti add_episode failed for %s: %s", name, e)
                return False

    # Add episodes with concurrency control
    tasks = [add_episode_with_semaphore(text, name) for text, name in texts_and_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    count = sum(1 for r in results if r is True and not isinstance(r, Exception))

    if count:
        logger.info(
            "Graphiti ingest doc_id=%s tenant_id=%s episodes=%d",
            doc_id[:8] if doc_id else "",
            tenant_id[:8] if tenant_id else "",
            count,
        )
    return count
