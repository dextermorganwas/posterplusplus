from __future__ import annotations
from typing import Any
import asyncio, logging
import httpx
log = logging.getLogger(__name__)
BASE = "https://api4.thetvdb.com/v4"
ART_BASE = "https://artworks.thetvdb.com"

class TVDBClient:
    def __init__(self, client: httpx.AsyncClient, key: str, pin: str = ""):
        self.client, self.key, self.pin = client, key, pin
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        if self._token: return self._token
        async with self._lock:
            if self._token: return self._token
            body = {"apikey": self.key}
            if self.pin: body["pin"] = self.pin
            r = await self.client.post(f"{BASE}/login", json=body)
            r.raise_for_status()
            self._token = r.json()["data"]["token"]
            return self._token

    async def get(self, path: str, **params):
        tok = await self.token()
        r = await self.client.get(f"{BASE}{path}", params=params or None, headers={"Authorization": f"Bearer {tok}"})
        if r.status_code == 401:
            self._token = None
            tok = await self.token()
            r = await self.client.get(f"{BASE}{path}", params=params or None, headers={"Authorization": f"Bearer {tok}"})
        r.raise_for_status()
        return r.json().get("data")

    async def resolve_id(self, media_type: str, *, tvdb_id: str | None, imdb_id: str | None, tmdb_id: str | None) -> int | None:
        if tvdb_id and tvdb_id.isdigit(): return int(tvdb_id)
        want = "series" if media_type in {"tv", "series"} else "movie"
        for remote in (imdb_id, tmdb_id):
            if not remote: continue
            data = await self.get(f"/search/remoteid/{remote}")
            if isinstance(data, list):
                for row in data:
                    rec = row.get(want) if isinstance(row, dict) else None
                    if isinstance(rec, dict) and rec.get("id"):
                        return int(rec["id"])
        return None

    async def artworks(self, media_type: str, tvdb_id: int) -> list[dict[str, Any]]:
        root = "series" if media_type in {"tv", "series"} else "movies"
        data = await self.get(f"/{root}/{tvdb_id}/extended", short="false")
        return (data or {}).get("artworks") or []

    @staticmethod
    def normalize_lang(code: str | None) -> str | None:
        if not code: return None
        mp = {"eng":"en","spa":"es","fra":"fr","deu":"de","ita":"it","por":"pt","jpn":"ja","kor":"ko","zho":"zh","rus":"ru","nld":"nl","pol":"pl","swe":"sv","dan":"da","nor":"no","fin":"fi","tur":"tr","ara":"ar","hin":"hi","ces":"cs","hun":"hu","ell":"el","heb":"he","tha":"th","ukr":"uk","ron":"ro"}
        return mp.get(code.lower(), code.lower())


    async def artwork_type_map(self, media_type: str) -> dict[int, str]:
        rows = await self.get('/artwork/types')
        out = {}
        wanted = 'series' if media_type in {'tv','series'} else 'movie'
        for row in rows or []:
            if (str(row.get('recordType') or '').lower() == wanted):
                text = f"{row.get('slug') or ''} {row.get('name') or ''}".lower()
                cat = 'logos' if ('clearlogo' in text or text.strip().endswith('logo') or ' logo' in text) else 'backgrounds' if ('background' in text or 'fanart' in text) else 'posters' if 'poster' in text else None
                if cat and row.get('id'):
                    out[int(row['id'])]=cat
        return out
