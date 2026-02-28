"""Semantic entities cache: fetch from API for entity resolution."""

from __future__ import annotations

import logging
from typing import Optional

from app.workflows.document_indexing.api_client import fetch_semantic_entities
from app.workflows.document_indexing.models import SemanticEntity

logger = logging.getLogger(__name__)


async def get_semantic_entities(tenant_id: Optional[str] = None) -> list[SemanticEntity]:
    """
    Fetch semantic entities from the API (semanticEntities query).
    Returns list of SemanticEntity for entity resolution workflow.
    """
    raw = await fetch_semantic_entities(tenant_id)
    entities: list[SemanticEntity] = []
    for item in raw:
        if isinstance(item, dict):
            entities.append(SemanticEntity.from_dict(item))
        else:
            logger.warning("Skipping non-dict semantic entity item: %s", type(item))
    logger.info(
        "Loaded %d semantic entities for entity resolution",
        len(entities),
    )
    return entities
