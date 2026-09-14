from __future__ import annotations
import os
from dataclasses import dataclass


def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = env_int("PORT", 8000)
    access_key: str = os.getenv("ACCESS_KEY", "").strip()

    tmdb_api_key: str = os.getenv("TMDB_API_KEY", "").strip()
    tvdb_api_key: str = os.getenv("TVDB_API_KEY", "").strip()
    tvdb_pin: str = os.getenv("TVDB_PIN", "").strip()
    mdblist_api_key: str = os.getenv("MDBLIST_API_KEY", "").strip()

    tmdb_poster_size: str = os.getenv("TMDB_POSTER_SIZE", "w780").strip()
    tmdb_backdrop_size: str = os.getenv("TMDB_BACKDROP_SIZE", "w1280").strip()
    tmdb_logo_size: str = os.getenv("TMDB_LOGO_SIZE", "w500").strip()

    art_cache_ttl_seconds: int = env_int("ART_CACHE_TTL_SECONDS", 60 * 60 * 24 * 30)
    selection_cache_ttl_seconds: int = env_int("SELECTION_CACHE_TTL_SECONDS", 60 * 60 * 24)
    metadata_cache_ttl_seconds: int = env_int("METADATA_CACHE_TTL_SECONDS", 60 * 60 * 24 * 7)
    top_rated_refresh_hours: int = env_int("TOP_RATED_REFRESH_HOURS", 24)
    top_rated_min_votes: int = env_int("TOP_RATED_MIN_VOTES", 500)

    tvdb_min_artworks: int = env_int("TVDB_MIN_ARTWORKS", 10)
    tvdb_min_logos: int = env_int("TVDB_MIN_LOGOS", 3)

    textless_backdrops_only: bool = env_bool("TEXTLESS_BACKDROPS_ONLY", True)
    enable_sashes: bool = env_bool("ENABLE_SASHES", True)
    sash_bottom_line_ratio: float = env_float("SASH_BOTTOM_LINE_RATIO", 0.012)
    sash_tab_height_ratio: float = env_float("SASH_TAB_HEIGHT_RATIO", 0.070)
    sash_tab_radius_ratio: float = env_float("SASH_TAB_RADIUS_RATIO", 0.016)
    sash_font_ratio: float = env_float("SASH_FONT_RATIO", 0.040)
    sash_side_pad_ratio: float = env_float("SASH_SIDE_PAD_RATIO", 0.025)
    sash_dark_threshold: float = env_float("SASH_DARK_THRESHOLD", 0.17)
    sash_force_gray_on_dark: bool = env_bool("SASH_FORCE_GRAY_ON_DARK", True)

    # Exact-ish PostersPlus priority vocabulary, but with the user's preferred
    # order as the default. Full slots are configurable in .env.
    sash_priority: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv(
            "SASH_PRIORITY",
            "trending,wins,gg_wins,festival,pic_noms,gg_noms,metacritic,top_rated,premiere,just_added,new_season,season_finale,returning,studio,director,cast,cult,true_story,short_film,mini_series,binge_ready,streaming,physical,cinema,airing,cancelled,ended"
        ).split(",") if x.strip()
    )

    trending_source_movie: str = os.getenv("TRENDING_SOURCE_MOVIE", "").strip()
    trending_source_tv: str = os.getenv("TRENDING_SOURCE_TV", "").strip()
    trending_count: int = env_int("TRENDING_FETCH_COUNT", 40)
    trending_broad_count: int = env_int("TRENDING_BROAD_FETCH_COUNT", 100)

    cache_dir: str = os.getenv("CACHE_DIR", "/app/cache")
    http_timeout_seconds: float = env_float("HTTP_TIMEOUT_SECONDS", 20.0)
    concurrency: int = max(1, env_int("UPSTREAM_CONCURRENCY", 12))

settings = Settings()
