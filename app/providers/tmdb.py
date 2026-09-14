from __future__ import annotations
from typing import Any
import io
import logging
import httpx
from PIL import Image

log = logging.getLogger(__name__)
BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"


def endpoint(media_type: str) -> str:
    return "tv" if media_type in {"tv", "series"} else "movie"


async def get_details(client: httpx.AsyncClient, key: str, media_type: str, tmdb_id: str) -> dict[str, Any]:
    r = await client.get(
        f"{BASE}/{endpoint(media_type)}/{tmdb_id}",
        params={"api_key": key, "append_to_response": "images,credits,external_ids,keywords", "include_image_language": "en,null"},
    )
    r.raise_for_status()
    return r.json()


async def get_images(client: httpx.AsyncClient, key: str, media_type: str, tmdb_id: str, languages: list[str]) -> dict[str, Any]:
    r = await client.get(
        f"{BASE}/{endpoint(media_type)}/{tmdb_id}/images",
        params={"api_key": key, "include_image_language": ",".join(dict.fromkeys([x for x in languages + ["en", "null"] if x is not None]))},
    )
    r.raise_for_status()
    return r.json()


def image_url(kind: str, path: str, settings) -> str:
    size = settings.tmdb_poster_size if kind == "poster" else settings.tmdb_backdrop_size if kind == "backdrop" else settings.tmdb_logo_size
    return f"{IMG}/{size}/{path.lstrip('/')}"


def lang_code(item: dict) -> str | None:
    x = item.get("iso_639_1")
    return x if x not in (None, "") else None


def pick(items: list[dict], *, wanted: list[str], textless: bool = False) -> dict | None:
    candidates = items
    if textless:
        candidates = [x for x in candidates if lang_code(x) is None]
    for lang in wanted:
        for x in candidates:
            if lang_code(x) == lang:
                return x
    neutral = [x for x in candidates if lang_code(x) is None]
    if neutral:
        return max(neutral, key=lambda x: (x.get("vote_average") or 0, x.get("vote_count") or 0))
    return None


def primary(details: dict, kind: str) -> str | None:
    if kind == "poster": return details.get("poster_path")
    if kind == "backdrop": return details.get("backdrop_path")
    return None
