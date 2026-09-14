from __future__ import annotations
import httpx

BASE = "https://images.metahub.space"

async def fetch(client: httpx.AsyncClient, kind: str, imdb_id: str) -> bytes | None:
    # Metahub uses these stable public URL patterns.
    path_kind = {"poster":"poster", "backdrop":"background", "logo":"logo"}[kind]
    size = "medium"
    url = f"{BASE}/{path_kind}/{size}/{imdb_id}/img"
    r = await client.get(url, follow_redirects=True)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content
