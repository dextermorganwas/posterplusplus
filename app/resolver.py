from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import httpx
from PIL import Image, ImageOps

from .config import settings
from .core.cache import FileCache
from .core.color import dominant_sash_color
from .core.discovery import extract_discovery_meta, pick_sash
from .core.sash import draw_status_sash
from .core.awards import parse_mdblist_awards
from .core.release_status import fetch_movie_release_info, fetch_recent_movie_digital_release_date, fetch_release_status
from .core.state import is_digital_release
from .providers import tmdb
from .providers.metahub import fetch as metahub_fetch
from .providers.tvdb import TVDBClient, lang_norm, is_series_level_artwork
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
    """TMDB media kind used by title endpoints."""
    return "tv" if media_type in {"tv", "series"} else "movie"


def _mdblist_media_kind(media_type: str) -> str:
    """MDBList media segment. MDBList uses `show`, not `tv`, for series."""
    return "show" if media_type in {"tv", "series"} else "movie"


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
        # A TVDB series payload can expose season/episode artwork alongside
        # series-level artwork. Exclude season/episode records before counting or
        # selecting so the 10/3-artwork density gates apply only to the show itself.
        if media_type in {"tv", "series"}:
            arts = [a for a in arts if is_series_level_artwork(a)]
        cat = [a for a in arts if type_map.get(a.get("type")) == wanted]
        threshold = settings.tvdb_min_logos if kind == "logo" else settings.tvdb_min_artworks
        if not bypass_count and len(cat) < threshold:
            return None

        order = [_LANG_MAP.get(x, x) for x in _lang_order(requested, original)]
        def al(a: dict) -> str:
            return str(a.get("language") or a.get("languageCode") or "").lower()
        if kind == "backdrop" and settings.textless_backdrops_only:
            cat = [a for a in cat if not al(a)]

        chosen = None
        for want in order:
            # IMPORTANT: preserve TVDB's returned artwork order. Do not score or
            # rerank by score/votes/primary flags for language-specific selection.
            for item in cat:
                if al(item) == want:
                    chosen = item
                    break
            if chosen is not None:
                break
        if chosen is None and kind == "backdrop" and settings.textless_backdrops_only:
            # For textless TVDB backdrops the API's neutral-art list is already the
            # candidate pool; take the first returned item, with no reranking.
            chosen = cat[0] if cat else None
        if chosen is None and bypass_count and cat:
            # Final relaxed TVDB fallback: honor an explicitly-primary artwork if
            # the API marks one; otherwise use the first returned artwork.
            primary = next((a for a in cat if a.get("isPrimary") or a.get("is_primary")), None)
            chosen = primary or cat[0]
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
        mdb_kind = _mdblist_media_kind(media_type)
        cache_key = f"{provider}:{mdb_kind}:{mid}"
        cached = self.cache.read_json("discovery", cache_key, settings.discovery_cache_ttl_seconds)
        if isinstance(cached, dict) and isinstance(cached.get("keywords"), list):
            return cached["keywords"]
        stale = self.cache.read_json_stale("discovery", cache_key)
        assert self.client is not None
        try:
            r = await self._get(
                f"https://api.mdblist.com/{provider}/{mdb_kind}/{mid}",
                params={"apikey": settings.mdblist_api_key, "append_to_response": "keyword"},
                timeout=10.0,
            )
        except Exception as exc:
            # A transient upstream failure must not erase a previously-known
            # keyword set. Keep stale discovery facts and make the next request
            # eligible for a retry after the normal cache window.
            if isinstance(stale, dict) and isinstance(stale.get("keywords"), list):
                log.warning("MDBList lookup failed for %s (%s): %r; using stale keywords", mid, type(exc).__name__, exc)
                return stale["keywords"]
            log.warning("MDBList lookup failed for %s (%s): %r", mid, type(exc).__name__, exc)
            return []

        if r.status_code == 429:
            if isinstance(stale, dict) and isinstance(stale.get("keywords"), list):
                log.warning("MDBList rate limited for %s; using stale keywords", mid)
                return stale["keywords"]
            log.warning("MDBList rate limited for %s", mid)
            return []
        if r.status_code in (400, 404):
            # These are normal title misses/invalid lookups, not application
            # failures. Negative-cache them so repeated poster requests do not
            # hit MDBList again during the discovery TTL.
            try:
                self.cache.write_json("discovery", cache_key, {"keywords": [], "missing": r.status_code == 404, "invalid": r.status_code == 400})
            except Exception as exc:
                log.debug("MDBList negative-cache write failed for %s: %r", mid, exc)
            return []
        if r.status_code != 200:
            if isinstance(stale, dict) and isinstance(stale.get("keywords"), list):
                log.warning("MDBList HTTP %s for %s; using stale keywords", r.status_code, mid)
                return stale["keywords"]
            log.warning("MDBList HTTP %s for %s", r.status_code, mid)
            return []

        try:
            payload = r.json()
            keywords = payload.get("keywords") or []
            if not isinstance(keywords, list):
                raise ValueError("MDBList keywords field is not a list")
        except Exception as exc:
            if isinstance(stale, dict) and isinstance(stale.get("keywords"), list):
                log.warning("MDBList JSON parse failed for %s (%s): %r; using stale keywords", mid, type(exc).__name__, exc)
                return stale["keywords"]
            log.warning("MDBList JSON parse failed for %s (%s): %r", mid, type(exc).__name__, exc)
            return []

        try:
            self.cache.write_json("discovery", cache_key, {"keywords": keywords})
        except Exception as exc:
            log.debug("MDBList cache write failed for %s: %r", mid, exc)
        return keywords

    async def _load_art_bytes(self, url: str, kind: str) -> bytes:
        cached = self.cache.read("art", url, "bin", settings.art_cache_ttl_seconds)
        if cached is not None:
            return cached
        r = await self._get(url, timeout=settings.http_timeout_seconds)
        r.raise_for_status()
        self.cache.write_atomic("art", url, "bin", r.content)
        return r.content

    async def _build_sash(self, raw: bytes, provider: str, details: dict, media_type: str, tmdb_id: str, imdb_id: str | None, source_url: str | None = None) -> tuple[bytes, str, str | None]:
        if not settings.enable_sashes:
            return raw, provider, None
        assert self.client is not None

        # Cache the completed composite image. This mirrors PostersPlus'
        # philosophy: expensive discovery should not happen on every poster
        # request. The cache key includes all inputs that can change the sash.
        sash_key = (
            f"v{settings.art_selection_algorithm_version}:"
            f"{provider}:{source_url or ''}:{tmdb_id}:{imdb_id or ''}:{media_type}:"
            f"{settings.sash_priority}:{settings.sash_dark_threshold}:"
            f"{settings.sash_force_gray_on_dark}:{settings.sash_tab_width_ratio}:"
            f"{settings.sash_font_ratio}:{settings.sash_side_pad_ratio}:"
            f"{settings.sash_bottom_inset_ratio}:{settings.sash_text_vertical_offset_ratio}:"
            f"{settings.sash_cache_ttl_seconds}"
        )
        cached = self.cache.read_json("sash", sash_key, settings.sash_cache_ttl_seconds)
        cached_bytes = self.cache.read("sash_image", sash_key, "jpg", settings.sash_cache_ttl_seconds)
        if isinstance(cached, dict) and cached_bytes is not None:
            return cached_bytes, provider, cached.get("label")

        async with self.image_sem:
            img = Image.open(io.BytesIO(raw)).convert("RGB")

        # The daily IMDb dataset is maintained by the background task started at
        # application startup. The request path only reads the local in-memory set.

        # Independent discovery sources run concurrently. Previously these were
        # awaited serially (MDBList -> trending -> release dates), which made a
        # single poster wait for the sum of several upstream latencies.
        keyword_task = asyncio.create_task(self._load_keywords(media_type, tmdb_id, imdb_id))
        trend_task = asyncio.create_task(self.trending.ranks(self.client, media_type, settings.tmdb_api_key))

        release_status = None
        recent_digital = None
        release_slots = {"release_status", "cinema", "streaming", "physical", "production", "ended", "cancelled", "airing"}
        needs_release = any(s in settings.sash_priority for s in release_slots)
        needs_recent_digital = media_type not in ("tv", "series") and bool({"just_added", "new_release", "digital_release"} & set(settings.sash_priority))
        release_task = None
        if needs_release or needs_recent_digital:
            release_task = asyncio.create_task(
                fetch_movie_release_info(self.client, tmdb_id, settings.tmdb_api_key, details.get("status"))
                if media_type not in ("tv", "series")
                else fetch_release_status(self.client, tmdb_id, settings.tmdb_api_key, media_type, details.get("status"))
            )

        await (asyncio.gather(keyword_task, trend_task, release_task) if release_task else asyncio.gather(keyword_task, trend_task))

        keywords = keyword_task.result()
        try:
            ranks = trend_task.result()
            trend_rank = ranks.get(str(tmdb_id))
        except Exception as exc:
            log.warning("Trending lookup failed (%s): %r", type(exc).__name__, exc)
            trend_rank = None

        if release_task:
            try:
                release_value = release_task.result()
                if media_type in ("tv", "series"):
                    release_status = release_value
                else:
                    info = release_value or {}
                    release_status = info.get("status")
                    d = info.get("digital_latest_date") or info.get("digital_date")
                    if d:
                        try:
                            from datetime import date
                            age = (date.today() - date.fromisoformat(str(d)[:10])).days
                            if 0 <= age <= 14:
                                recent_digital = str(d)[:10]
                        except (TypeError, ValueError):
                            recent_digital = None
            except Exception as exc:
                log.warning("Release-status lookup failed (%s): %r", type(exc).__name__, exc)

        if release_status in ("Cinema", "Production") and is_digital_release(imdb_id):
            release_status = "Streaming"

        wins, noms = parse_mdblist_awards(keywords, tmdb_id=tmdb_id, media_type=media_type)
        is_top_rated = self.toprated.is_top(imdb_id)

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
            try:
                self.cache.write_atomic("sash_image", sash_key, "jpg", raw)
                self.cache.write_json("sash", sash_key, {"label": None})
            except Exception as exc:
                log.debug("No-sash cache write failed for %s: %r", tmdb_id, exc)
            return raw, provider, None

        label, _stype = picked
        color, text = dominant_sash_color(img, settings.sash_dark_threshold, settings.sash_force_gray_on_dark)
        out = draw_status_sash(img, label, color, text, settings)
        buf = io.BytesIO(); out.save(buf, format="JPEG", quality=92, optimize=True)
        body = buf.getvalue()
        try:
            self.cache.write_atomic("sash_image", sash_key, "jpg", body)
            self.cache.write_json("sash", sash_key, {"label": label})
        except Exception as exc:
            log.debug("Sash cache write failed for %s: %r", tmdb_id, exc)
        return body, provider, label

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
        sel_key = f"v{settings.art_selection_algorithm_version}:{kind}:{_media_kind(media_type)}:{tmdb_id or ''}:{imdb_id or ''}:{tvdb_id or ''}:{lang}:{settings.textless_backdrops_only}:{settings.tvdb_min_artworks}:{settings.tvdb_min_logos}:{settings.tmdb_poster_size}:{settings.tmdb_backdrop_size}:{settings.tmdb_logo_size}"
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
            # Normalize every sashed poster to PostersPlus's 500x750 output canvas.
            # This makes the bottom sash occupy the same geometry regardless of
            # whether TMDB/TVDB returned 2:3, 680x1000, or another near-poster ratio.
            async with self.image_sem:
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                image = ImageOps.fit(
                    image,
                    (500, 750),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=92, optimize=True)
                raw = buf.getvalue()
            return await self._build_sash(raw, provider or "unknown", details or {}, media_type, str(tmdb_id or ""), imdb_id, selected_url)
        return raw, provider, None
