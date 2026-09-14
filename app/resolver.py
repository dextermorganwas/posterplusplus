from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import httpx
from PIL import Image

from .config import settings
from .core.cache import FileCache
from .core.color import dominant_sash_color
from .core.discovery import extract_discovery_meta, pick_sash
from .core.sash import draw_status_sash
from .core.awards import parse_mdblist_awards
from .core.release_status import fetch_recent_movie_digital_release_date, fetch_release_status
from .core.state import is_digital_release
from .providers import tmdb
from .providers.metahub import fetch as metahub_fetch
from .providers.tvdb import TVDBClient, lang_norm
from .toprated import IMDbRatings
from .trending import Trending

log = logging.getLogger(__name__)

_LANG_MAP = {
    "en":"eng", "es":"spa", "fr":"fra", "de":"deu", "it":"ita", "pt":"por",
    "ja":"jpn", "ko":"kor", "zh":"zho", "ru":"rus", "nl":"nld", "pl":"pol",
    "sv":"swe", "da":"dan", "no":"nor", "fi":"fin", "tr":"tur", "ar":"ara",
    "hi":"hin", "cs":"ces", "hu":"hun", "el":"ell", "he":"heb", "th":"tha",
    "uk":"ukr", "ro":"ron",
}


def _media_kind(media_type: str) -> str:
    return "tv" if media_type in {"tv", "series"} else "movie"


def _lang_order(requested: str | None, original: str | None) -> list[str]:
    out: list[str] = []
    for x in (requested or "en", "en", original):
        if x and x not in out:
            out.append(x)
    return out


class Resolver:
    def __init__(self) -> None:
        self.cache = FileCache(settings.cache_dir)
        self.inflight: dict[str, asyncio.Task] = {}
        self.guard = asyncio.Lock()
        self.client: httpx.AsyncClient | None = None
        self.upstream_sem = asyncio.Semaphore(settings.upstream_concurrency)
        self.image_sem = asyncio.Semaphore(settings.image_processing_concurrency)
        self.toprated = IMDbRatings(
            f"{settings.cache_dir}/title.ratings.tsv.gz",
            settings.top_rated_refresh_hours,
            settings.top_rated_min_votes,
            threshold=settings.top_rated_threshold,
        )
        self.trending = Trending(self.cache)
        self.stop_event = asyncio.Event()
        self.background_tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self.client is None:
            timeout = httpx.Timeout(settings.http_timeout_seconds)
            limits = httpx.Limits(max_connections=max(8, settings.upstream_concurrency * 2), max_keepalive_connections=settings.upstream_concurrency)
            self.client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "MediaArtRouter/1.0"}, limits=limits, follow_redirects=True)

    async def stop(self) -> None:
        self.stop_event.set()
        for task in self.background_tasks:
            task.cancel()
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        assert self.client is not None
        async with self.upstream_sem:
            return await self.client.get(url, **kwargs)

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        assert self.client is not None
        async with self.upstream_sem:
            return await self.client.post(url, **kwargs)

    async def coalesced(self, key: str, coro_factory):
        async with self.guard:
            task = self.inflight.get(key)
            if task is None or task.done():
                task = asyncio.create_task(coro_factory())
                self.inflight[key] = task
        try:
            return await task
        finally:
            async with self.guard:
                if self.inflight.get(key) is task:
                    self.inflight.pop(key, None)

    async def _resolve_identity(self, media_type: str, tmdb_id: str | None, imdb_id: str | None, tvdb_id: str | None) -> tuple[str | None, str | None, str | None, str]:
        """Return (tmdb_id, imdb_id, tvdb_id, media_type). Never discards IDs."""
        kind = _media_kind(media_type)
        assert self.client is not None

        if not tmdb_id and imdb_id and settings.tmdb_api_key:
            try:
                found = await tmdb.find_by_imdb(self.client, settings.tmdb_api_key, imdb_id, kind)
                if found:
                    tmdb_id, found_type = found
                    kind = found_type
                    media_type = found_type
            except Exception as exc:
                log.warning("TMDB IMDb resolution failed for %s: %s", imdb_id, exc)

        if not tmdb_id and tvdb_id and settings.tvdb_api_key:
            try:
                tv = TVDBClient(self.client, settings.tvdb_api_key, settings.tvdb_pin)
                ext = await tv.extended(kind, int(tvdb_id)) if str(tvdb_id).isdigit() else None
                for remote in (ext or {}).get("remoteIds") or []:
                    source = str(remote.get("sourceName") or remote.get("source") or "").lower()
                    rid = str(remote.get("id") or remote.get("remoteId") or "")
                    if rid.startswith("tt") and not imdb_id:
                        imdb_id = rid
                    if ("tmdb" in source or "the movie database" in source) and rid.isdigit() and not tmdb_id:
                        tmdb_id = rid
            except Exception as exc:
                log.debug("TVDB remote identity lookup failed for %s: %s", tvdb_id, exc)

        return tmdb_id, imdb_id, tvdb_id, media_type

    async def _fetch_details(self, media_type: str, tmdb_id: str) -> dict:
        key = f"{media_type}:{tmdb_id}"
        cached = self.cache.read_json("metadata", key, settings.metadata_cache_ttl_seconds)
        if cached is not None:
            return cached
        assert self.client is not None
        data = await tmdb.get_details(self.client, settings.tmdb_api_key, media_type, tmdb_id)
        self.cache.write_json("metadata", key, data)
        return data

    async def _tvdb_selection(self, media_type: str, kind: str, tvdb_id: str | None, imdb_id: str | None, tmdb_id: str | None, requested: str | None, original: str | None, bypass_count: bool = False) -> tuple[str, str] | None:
        if not settings.tvdb_api_key:
            return None
        assert self.client is not None
        tv = TVDBClient(self.client, settings.tvdb_api_key, settings.tvdb_pin)
        tid = await tv.resolve_id(media_type, tvdb_id=tvdb_id, imdb_id=imdb_id, tmdb_id=tmdb_id)
        if not tid:
            return None
        arts = await tv.artworks(media_type, tid)
        type_map = await tv.artwork_type_map()
        wanted = {"poster":"posters", "backdrop":"backdrops", "logo":"logos"}[kind]
        cat = [a for a in arts if type_map.get(a.get("type")) == wanted]
        threshold = settings.tvdb_min_logos if kind == "logo" else settings.tvdb_min_artworks
        if not bypass_count and len(cat) < threshold:
            return None

        order = [_LANG_MAP.get(x, x) for x in _lang_order(requested, original)]
        def al(a: dict) -> str:
            return str(a.get("language") or a.get("languageCode") or "").lower()
        def score(a: dict) -> tuple[float, float, float]:
            try: s=float(a.get("score") or 0)
            except (ValueError, TypeError): s=0.0
            try: v=float(a.get("vote_average") or 0)
            except (ValueError, TypeError): v=0.0
            primary=1.0 if a.get("isPrimary") or a.get("is_primary") else 0.0
            return (primary, s, v)

        if kind == "backdrop" and settings.textless_backdrops_only:
            cat = [a for a in cat if not al(a)]

        chosen = None
        for want in order:
            xs = [a for a in cat if al(a) == want]
            if xs:
                chosen = max(xs, key=score)
                break
        if chosen is None and kind == "backdrop" and settings.textless_backdrops_only:
            # A language-neutral TVDB background is the textless candidate pool; do not
            # fall through to language-bearing fanart, because the caller explicitly
            # requested textless-only backdrops.
            return None
        if chosen is None and bypass_count and cat:
            # Relaxed final fallback: exact language first above, then strongest primary art.
            chosen = max(cat, key=score)
        if chosen is None:
            return None
        url = chosen.get("image") or chosen.get("image_url") or ""
        if not url:
            return None
        return (url if str(url).startswith("http") else "https://artworks.thetvdb.com/" + str(url).lstrip("/"), "tvdb-fallback" if bypass_count else "tvdb")

    async def _tmdb_selection(self, kind: str, details: dict, media_type: str, requested: str | None, original: str | None) -> str | None:
        imgs = details.get("images") or {}
        order = _lang_order(requested, original)
        chosen = tmdb.pick(imgs.get({"poster":"posters","backdrop":"backdrops","logo":"logos"}[kind], []), order, textless=(kind == "backdrop" and settings.textless_backdrops_only))
        if chosen and chosen.get("file_path"):
            return tmdb.image_url(kind, chosen["file_path"], settings)
        # When original language is different and wasn't included in the initial metadata request,
        # explicitly ask for it now, preserving the exact English -> original philosophy.
        if original and original != "en":
            imgs2 = await tmdb.get_images(self.client, settings.tmdb_api_key, media_type, str(details["id"]), ["en", original])
            chosen = tmdb.pick(imgs2.get({"poster":"posters","backdrop":"backdrops","logo":"logos"}[kind], []), order, textless=(kind == "backdrop" and settings.textless_backdrops_only))
            if chosen and chosen.get("file_path"):
                return tmdb.image_url(kind, chosen["file_path"], settings)
        return None

    async def _load_keywords(self, media_type: str, tmdb_id: str, imdb_id: str | None) -> list[dict]:
        if not settings.mdblist_api_key:
            return []
        provider = "imdb" if imdb_id else "tmdb"
        mid = imdb_id or tmdb_id
        cache_key = f"{provider}:{_media_kind(media_type)}:{mid}"
        cached = self.cache.read_json("discovery", cache_key, settings.discovery_cache_ttl_seconds)
        if isinstance(cached, dict) and isinstance(cached.get("keywords"), list):
            return cached["keywords"]
        assert self.client is not None
        try:
            r = await self._get(f"https://api.mdblist.com/{provider}/{_media_kind(media_type)}/{mid}", params={"apikey": settings.mdblist_api_key, "append_to_response": "keyword"}, timeout=10.0)
            if r.status_code == 429:
                log.warning("MDBList rate limited for %s", mid)
                return []
            if r.status_code != 200:
                return []
            keywords = r.json().get("keywords") or []
            self.cache.write_json("discovery", cache_key, {"keywords": keywords})
            return keywords
        except Exception as exc:
            log.warning("MDBList keyword lookup failed for %s: %s", mid, exc)
            return []

    async def _load_art_bytes(self, url: str, kind: str) -> bytes:
        cached = self.cache.read("art", url, "bin", settings.art_cache_ttl_seconds)
        if cached is not None:
            return cached
        r = await self._get(url, timeout=settings.http_timeout_seconds)
        r.raise_for_status()
        self.cache.write_atomic("art", url, "bin", r.content)
        return r.content

    async def _build_sash(self, raw: bytes, details: dict, media_type: str, tmdb_id: str, imdb_id: str | None) -> tuple[bytes, str | None]:
        if not settings.enable_sashes:
            return raw, None
        assert self.client is not None
        async with self.image_sem:
            img = Image.open(io.BytesIO(raw)).convert("RGB")

        # Top-rated dataset is local after refresh and only needs an IMDb id.
        await self.toprated.refresh_if_needed(self.client)
        is_top_rated = self.toprated.is_top(imdb_id)

        keywords = await self._load_keywords(media_type, tmdb_id, imdb_id)
        wins, noms = parse_mdblist_awards(keywords, tmdb_id=tmdb_id)

        try:
            ranks = await self.trending.ranks(self.client, media_type, settings.tmdb_api_key)
            trend_rank = ranks.get(str(tmdb_id))
        except Exception as exc:
            log.warning("Trending lookup failed: %s", exc)
            trend_rank = None

        tmdb_data = {
            "id": details.get("id"),
            "original_language": details.get("original_language"),
            "production_companies": details.get("production_companies") or [],
            "credits": details.get("credits") or {},
            "runtime": details.get("runtime"),
            "number_of_seasons": details.get("number_of_seasons") or 0,
            "number_of_episodes": details.get("number_of_episodes") or 0,
            "tmdb_status": details.get("status"),
            "tmdb_release_date": details.get("release_date") or details.get("first_air_date"),
            "next_episode": details.get("next_episode_to_air"),
            "last_episode": details.get("last_episode_to_air"),
            "seasons": details.get("seasons") or [],
        }

        release_status = None
        recent_digital = None
        release_slots = {"release_status", "cinema", "streaming", "physical", "production", "ended", "cancelled", "airing"}
        if any(s in settings.sash_priority for s in release_slots):
            try:
                release_status = await fetch_release_status(self.client, tmdb_id, settings.tmdb_api_key, media_type, details.get("status"))
            except Exception as exc:
                log.warning("Release-status lookup failed: %s", exc)
            if release_status in ("Cinema", "Production") and is_digital_release(imdb_id):
                release_status = "Streaming"

        if media_type not in ("tv", "series") and ({"just_added", "new_release", "digital_release"} & set(settings.sash_priority)):
            try:
                recent_digital = await fetch_recent_movie_digital_release_date(self.client, tmdb_id, settings.tmdb_api_key, details.get("status"))
            except Exception as exc:
                log.warning("Recent digital-date lookup failed: %s", exc)

        meta = extract_discovery_meta(
            tmdb_data=tmdb_data,
            media_type=media_type,
            award_wins=wins,
            award_noms=noms,
            trending_rank=trend_rank,
            tmdb_id=tmdb_id,
            release_date=details.get("release_date") or details.get("first_air_date"),
            keywords=keywords,
            is_cult_override="cult-classic" in {(k.get("name") or "").lower() for k in keywords} or "cult-film" in {(k.get("name") or "").lower() for k in keywords},
            is_true_story_override="based-on-true-story" in {(k.get("name") or "").lower() for k in keywords},
            is_metacritic_override="metacritic-must-see" in {(k.get("name") or "").lower() for k in keywords},
            is_digital_release_override=bool(is_digital_release(imdb_id)),
            release_status_override=release_status,
            recent_digital_release_date=recent_digital,
        )
        setattr(meta, "is_top_rated", is_top_rated)

        picked = None
        for slot in settings.sash_priority:
            if slot == "top_rated":
                if is_top_rated:
                    picked = ("Top Rated", "win")
                    break
            else:
                p = pick_sash(meta, [slot])
                if p:
                    picked = p
                    break
        if not picked:
            return raw, None
        label, _stype = picked
        color, text = dominant_sash_color(img, settings.sash_dark_threshold, settings.sash_force_gray_on_dark)
        out = draw_status_sash(img, label, color, text, settings)
        buf = io.BytesIO(); out.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue(), label

    async def select_art(self, kind: str, media_type: str, tmdb_id: str | None, imdb_id: str | None = None, tvdb_id: str | None = None, lang: str = "en", with_sash: bool = False):
        requested = kind + ":" + _media_kind(media_type) + ":" + str(tmdb_id or "") + ":" + str(imdb_id or "") + ":" + str(tvdb_id or "") + ":" + str(lang) + ":" + str(with_sash)
        return await self.coalesced(requested, lambda: self._select_art_uncached(kind, media_type, tmdb_id, imdb_id, tvdb_id, lang, with_sash))

    async def _select_art_uncached(self, kind, media_type, tmdb_id, imdb_id, tvdb_id, lang, with_sash):
        if not settings.tmdb_api_key and not settings.tvdb_api_key:
            raise RuntimeError("At least one of TMDB_API_KEY or TVDB_API_KEY is required")

        tmdb_id, imdb_id, tvdb_id, media_type = await self._resolve_identity(media_type, tmdb_id, imdb_id, tvdb_id)
        if not tmdb_id and not tvdb_id and not imdb_id:
            raise ValueError("No usable media ID supplied")

        details = None
        original = None
        if tmdb_id and settings.tmdb_api_key:
            details = await self._fetch_details(media_type, str(tmdb_id))
            original = details.get("original_language")
            # TMDB external_ids are the canonical cross-provider fallback.
            ext = details.get("external_ids") or {}
            imdb_id = imdb_id or ext.get("imdb_id")
            tvdb_id = tvdb_id or (str(ext.get("tvdb_id")) if ext.get("tvdb_id") else None)

        # Selection cache stores only the resolved source URL/provider.  Sashes are
        # deliberately rendered after this layer because their facts are more volatile.
        sel_key = f"{kind}:{_media_kind(media_type)}:{tmdb_id or ''}:{imdb_id or ''}:{tvdb_id or ''}:{lang}:{settings.textless_backdrops_only}:{settings.tvdb_min_artworks}:{settings.tvdb_min_logos}:{settings.tmdb_poster_size}:{settings.tmdb_backdrop_size}:{settings.tmdb_logo_size}"
        cached_sel = self.cache.read_json("selection", sel_key, settings.selection_cache_ttl_seconds)
        selected_url = None
        provider = None
        raw = None
        if isinstance(cached_sel, dict) and cached_sel.get("url"):
            selected_url = cached_sel["url"]
            provider = cached_sel.get("provider") or "cached"
            try:
                raw = await self._load_art_bytes(selected_url, kind)
            except Exception:
                raw = None

        if raw is None:
            # 1) TVDB first with the density gate, exact language order requested.
            tvdb_sel = await self._tvdb_selection(media_type, kind, tvdb_id, imdb_id, str(tmdb_id) if tmdb_id else None, lang, original, False)
            if tvdb_sel:
                selected_url, provider = tvdb_sel
                raw = await self._load_art_bytes(selected_url, kind)
            else:
                # 2) TMDB English -> original language.
                provider = "tmdb"
                if details:
                    selected_url = await self._tmdb_selection(kind, details, media_type, lang, original)
                if selected_url:
                    raw = await self._load_art_bytes(selected_url, kind)
                else:
                    # 3) Metahub (IMDb) only when available.
                    if imdb_id and self.client:
                        raw = await metahub_fetch(self.client, kind, imdb_id)
                    if raw:
                        provider = "metahub"
                        selected_url = f"https://images.metahub.space/{'poster' if kind == 'poster' else 'background' if kind == 'backdrop' else 'logo'}/medium/{imdb_id}/img"
                    else:
                        # 4) Last-resort TVDB with density rule disabled.
                        tvdb_sel = await self._tvdb_selection(media_type, kind, tvdb_id, imdb_id, str(tmdb_id) if tmdb_id else None, lang, original, True)
                        if tvdb_sel:
                            selected_url, provider = tvdb_sel
                            raw = await self._load_art_bytes(selected_url, kind)
                        else:
                            # 5) Whatever TMDB primary artwork is available.
                            if details:
                                p = tmdb.primary(details, kind)
                                if p:
                                    selected_url = tmdb.image_url(kind, p, settings)
                                    provider = "tmdb-primary"
                                    raw = await self._load_art_bytes(selected_url, kind)
                            if raw is None:
                                raise httpx.HTTPStatusError("No usable artwork", request=httpx.Request("GET", "http://localhost"), response=httpx.Response(404))
            if selected_url and provider:
                self.cache.write_json("selection", sel_key, {"url": selected_url, "provider": provider})

        if kind == "poster" and with_sash:
            return await self._build_sash(raw, details or {}, media_type, str(tmdb_id or ""), imdb_id)
        return raw, provider, None
