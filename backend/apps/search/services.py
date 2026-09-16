"""Meilisearch indexing and querying.

Search is a phase-two feature, so every entry point degrades gracefully: with
`SEARCH_ENABLED=false` (or Meilisearch unreachable) indexing is a no-op and
queries fall back to a Postgres `icontains` scan. That keeps search working in
development without another service to run, and keeps a Meilisearch outage from
taking the API down.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

COMPETITIONS_INDEX = "competitions"
PARTICIPANTS_INDEX = "participants"
POSTS_INDEX = "posts"

INDEX_SETTINGS: dict[str, dict[str, Any]] = {
    COMPETITIONS_INDEX: {
        "searchableAttributes": ["name", "description", "sport"],
        "filterableAttributes": ["sport", "status", "is_private", "owner_id"],
        "sortableAttributes": ["created_at"],
    },
    PARTICIPANTS_INDEX: {
        "searchableAttributes": ["name", "short_name", "description"],
        "filterableAttributes": ["competition_id"],
    },
    POSTS_INDEX: {
        "searchableAttributes": ["body", "author_name"],
        "filterableAttributes": ["competition_id", "author_id"],
        "sortableAttributes": ["created_at"],
    },
}


@lru_cache(maxsize=1)
def get_client():
    if not settings.SEARCH_ENABLED:
        return None
    try:
        import meilisearch

        return meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
    except Exception as exc:
        logger.warning("Meilisearch unavailable: %s", exc)
        return None


def ensure_indexes() -> None:
    client = get_client()
    if client is None:
        return
    for index_name, config in INDEX_SETTINGS.items():
        try:
            client.create_index(index_name, {"primaryKey": "id"})
        except Exception as exc:
            # Almost always "index already exists", which is the normal case on
            # every start after the first.
            logger.debug("Could not create index %s: %s", index_name, exc)
        try:
            client.index(index_name).update_settings(config)
        except Exception as exc:
            logger.warning("Could not configure index %s: %s", index_name, exc)


def index_documents(index_name: str, documents: list[dict]) -> None:
    client = get_client()
    if client is None or not documents:
        return
    try:
        client.index(index_name).add_documents(documents)
    except Exception as exc:
        logger.warning("Indexing into %s failed: %s", index_name, exc)


def delete_document(index_name: str, document_id: str) -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.index(index_name).delete_document(document_id)
    except Exception as exc:
        logger.warning("Deleting %s from %s failed: %s", document_id, index_name, exc)


# --- Document builders ------------------------------------------------------


def competition_document(competition) -> dict:
    return {
        "id": str(competition.id),
        "name": competition.name,
        "slug": competition.slug,
        "description": competition.description,
        "sport": competition.sport,
        "status": competition.status,
        "is_private": competition.is_private,
        "owner_id": str(competition.owner_id),
        "logo_url": competition.logo_url,
        "created_at": competition.created_at.timestamp(),
    }


def participant_document(participant) -> dict:
    return {
        "id": str(participant.id),
        "competition_id": str(participant.competition_id),
        "name": participant.name,
        "short_name": participant.short_name,
        "description": participant.description,
        "logo_url": participant.logo_url,
    }


def post_document(post) -> dict:
    return {
        "id": str(post.id),
        "competition_id": str(post.competition_id),
        "author_id": str(post.author_id),
        "author_name": post.author.get_full_name(),
        "body": post.body,
        "created_at": post.created_at.timestamp(),
    }


# --- Querying ---------------------------------------------------------------


def search(index_name: str, query: str, *, filters: str = "", limit: int = 20) -> list[dict]:
    client = get_client()
    if client is None:
        return _postgres_fallback(index_name, query, limit)

    try:
        result = client.index(index_name).search(
            query, {"limit": limit, **({"filter": filters} if filters else {})}
        )
        return result.get("hits", [])
    except Exception as exc:
        logger.warning("Meilisearch query failed, falling back to Postgres: %s", exc)
        return _postgres_fallback(index_name, query, limit)


def _postgres_fallback(index_name: str, query: str, limit: int) -> list[dict]:
    from django.db.models import Q

    if index_name == COMPETITIONS_INDEX:
        from apps.competitions.models import Competition

        rows = Competition.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(sport__icontains=query),
            is_private=False,
        ).select_related("owner")[:limit]
        return [competition_document(row) for row in rows]

    if index_name == PARTICIPANTS_INDEX:
        from apps.competitions.models import Participant

        rows = Participant.objects.filter(name__icontains=query)[:limit]
        return [participant_document(row) for row in rows]

    if index_name == POSTS_INDEX:
        from apps.social.models import Post

        rows = (
            Post.objects.alive()
            .filter(body__icontains=query, competition__is_private=False)
            .select_related("author")[:limit]
        )
        return [post_document(row) for row in rows]

    return []
