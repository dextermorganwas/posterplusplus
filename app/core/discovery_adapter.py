from __future__ import annotations
from typing import Any
from .discovery import DiscoveryMeta, extract_discovery_meta, pick_sash
from .awards import parse_mdblist_awards


def build_discovery(
    *,
    tmdb_data: dict[str, Any],
    media_type: str,
    tmdb_id: str | int,
    keywords: list[dict] | None,
    trending_rank: int | None,
    top_rated: bool,
    settings,
) -> DiscoveryMeta:
    wins, noms = parse_mdblist_awards(keywords or [], tmdb_id=tmdb_id, media_type=media_type)
    meta = extract_discovery_meta(
        tmdb_data,
        media_type,
        wins,
        noms,
        trending_rank,
        tmdb_id=tmdb_id,
        keywords=keywords,
    )
    meta.is_metacritic_must_see = meta.is_metacritic_must_see
    if top_rated:
        # Reuse a free-form attribute rather than changing the upstream module.
        setattr(meta, "is_top_rated", True)
    else:
        setattr(meta, "is_top_rated", False)
    return meta


def pick_sash_with_top_rated(meta, priority: list[str]) -> tuple[str, str] | None:
    # discovery.py is the extracted PostersPlus picker. top_rated is deliberately
    # injected here so the original priority picker stays untouched.
    for slot in priority:
        if slot == "top_rated":
            if getattr(meta, "is_top_rated", False):
                return "Top Rated", "win"
            continue
        got = pick_sash(meta, [slot])
        if got:
            return got
    return None
