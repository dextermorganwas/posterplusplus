from __future__ import annotations
import os
from dataclasses import dataclass

def env_bool(name, default=False):
    v=os.getenv(name); return default if v is None else v.strip().lower() in {"1","true","yes","on"}
def env_int(name, default):
    try: return int(os.getenv(name,str(default)))
    except ValueError: return default
def env_float(name, default):
    try: return float(os.getenv(name,str(default)))
    except ValueError: return default

@dataclass(frozen=True)
class Settings:
    host: str=os.getenv("HOST","0.0.0.0")
    port: int=env_int("PORT",8000)
    access_key: str=os.getenv("ACCESS_KEY","").strip()
    tmdb_api_key: str=os.getenv("TMDB_API_KEY","").strip()
    tvdb_api_key: str=os.getenv("TVDB_API_KEY","").strip()
    tvdb_pin: str=os.getenv("TVDB_PIN","").strip()
    mdblist_api_key: str=os.getenv("MDBLIST_API_KEY","").strip()
    tmdb_poster_size: str=os.getenv("TMDB_POSTER_SIZE","w500").strip()
    tmdb_backdrop_size: str=os.getenv("TMDB_BACKDROP_SIZE","w1280").strip()
    tmdb_logo_size: str=os.getenv("TMDB_LOGO_SIZE","w500").strip()
    art_cache_ttl_seconds: int=env_int("ART_CACHE_TTL_SECONDS",2592000)
    selection_cache_ttl_seconds: int=env_int("SELECTION_CACHE_TTL_SECONDS",86400)
    metadata_cache_ttl_seconds: int=env_int("METADATA_CACHE_TTL_SECONDS",604800)
    discovery_cache_ttl_seconds: int=env_int("DISCOVERY_CACHE_TTL_SECONDS",21600)
    top_rated_refresh_hours: int=env_int("TOP_RATED_REFRESH_HOURS",24)
    top_rated_min_votes: int=env_int("TOP_RATED_MIN_VOTES",500)
    top_rated_threshold: float=env_float("TOP_RATED_THRESHOLD",8.5)
    tvdb_min_artworks: int=env_int("TVDB_MIN_ARTWORKS",10)
    tvdb_min_logos: int=env_int("TVDB_MIN_LOGOS",3)
    textless_backdrops_only: bool=env_bool("TEXTLESS_BACKDROPS_ONLY",True)
    enable_sashes: bool=env_bool("ENABLE_SASHES",True)
    sash_bottom_line_ratio: float=env_float("SASH_BOTTOM_LINE_RATIO",0.014)
    sash_tab_height_ratio: float=env_float("SASH_TAB_HEIGHT_RATIO",0.085)
    sash_tab_radius_ratio: float=env_float("SASH_TAB_RADIUS_RATIO",0.018)
    sash_font_ratio: float=env_float("SASH_FONT_RATIO",0.055)
    sash_side_pad_ratio: float=env_float("SASH_SIDE_PAD_RATIO",0.030)
    sash_min_tab_width_ratio: float=env_float("SASH_MIN_TAB_WIDTH_RATIO",0.32)
    sash_max_tab_width_ratio: float=env_float("SASH_MAX_TAB_WIDTH_RATIO",0.70)
    sash_tab_width_ratio: float=env_float("SASH_TAB_WIDTH_RATIO",0.35)
    sash_dark_threshold: float=env_float("SASH_DARK_THRESHOLD",0.17)
    sash_force_gray_on_dark: bool=env_bool("SASH_FORCE_GRAY_ON_DARK",True)
    sash_bottom_inset_ratio: float=env_float("SASH_BOTTOM_INSET_RATIO",0.012)
    sash_text_vertical_offset_ratio: float=env_float("SASH_TEXT_VERTICAL_OFFSET_RATIO",0.004)
    sash_priority: tuple[str,...]=tuple(x.strip() for x in os.getenv(
        "SASH_PRIORITY",
        "trending,wins,gg_wins,festival,pic_noms,metacritic,gg_noms,top_rated,premiere,new_release,just_added,new_season,season_finale,studio,director,cast,cult,true_story,short_film,mini_series,binge_ready,returning,airing,cancelled,ended,cinema"
    ).split(",") if x.strip())
    trending_source_movie: str=os.getenv("TRENDING_SOURCE_MOVIE","").strip()
    trending_source_tv: str=os.getenv("TRENDING_SOURCE_TV","").strip()
    trending_count: int=env_int("TRENDING_FETCH_COUNT",40)
    trending_broad_count: int=env_int("TRENDING_BROAD_FETCH_COUNT",100)
    trending_source_max_items: int=max(1,env_int("TRENDING_SOURCE_MAX_ITEMS",500))
    trending_source_retry_seconds: int=max(30,env_int("TRENDING_SOURCE_RETRY_SECONDS",300))
    http_timeout_seconds: float=env_float("HTTP_TIMEOUT_SECONDS",20.0)
    upstream_concurrency: int=max(1,env_int("UPSTREAM_CONCURRENCY",12))
    image_processing_concurrency: int=max(1,env_int("IMAGE_PROCESSING_CONCURRENCY",2))
    cache_dir: str=os.getenv("CACHE_DIR","/app/cache")
    digital_release_min_age_days: int=max(0,env_int("DIGITAL_RELEASE_MIN_AGE_DAYS",1))
    digital_release_max_age_days: int=max(1,env_int("DIGITAL_RELEASE_MAX_AGE_DAYS",30))
    cinema_max_age_years: int=max(0,env_int("CINEMA_MAX_AGE_YEARS",3))
    art_selection_algorithm_version: int=max(1,env_int("ART_SELECTION_ALGORITHM_VERSION",4))
settings=Settings()
# Keep compatibility for exact extracted modules that refer to module-level names.
TRENDING_FETCH_COUNT=settings.trending_count
TRENDING_BROAD_FETCH_COUNT=settings.trending_broad_count
