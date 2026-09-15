from __future__ import annotations
import logging
from datetime import date, datetime, time as dtime
import httpx
from app.config import settings
from app.core.state import (
    get_cached_movie_release_info, set_cached_movie_release_info,
    get_cached_release_status, set_cached_release_status,
    release_status_expiry,
)
log=logging.getLogger(__name__)


def _parse(value):
    try: return date.fromisoformat((value or "")[:10])
    except (TypeError, ValueError): return None


def _compute_movie_status(theatrical_date, digital_date, physical_date, tmdb_status, premiere_date=None):
    today=date.today()
    if physical_date and physical_date <= today: return "Physical"
    if digital_date and digital_date <= today: return "Streaming"
    if theatrical_date and theatrical_date <= today:
        if settings.cinema_max_age_years > 0 and (today-theatrical_date).days > settings.cinema_max_age_years*365:
            return "Streaming"
        return "Cinema"
    if tmdb_status == "Released" and not any(
        d is not None and d > today
        for d in (theatrical_date, digital_date, physical_date, premiere_date)
    ):
        # TMDB can flip a film to Released before its first actual release date.
        # If it has no future theatrical/digital/physical/premiere date, it is safe
        # to treat it as already out somewhere; a future date proves otherwise.
        return "Streaming"
    return "Production"


def _release_info_is_current(info: dict) -> bool:
    """Legacy rows without premiere_date are refreshed once after date-model changes."""
    if "premiere_date" in info:
        return True
    return any(info.get(k) for k in ("theatrical_date", "digital_date", "physical_date"))


def _release_info_expiry(info: dict) -> int:
    upcoming=[]; today=date.today()
    for key in ("theatrical_date","digital_date","physical_date","premiere_date"):
        d=_parse(info.get(key))
        if d and d>today:
            upcoming.append(int(datetime.combine(d,dtime.min).timestamp()))
    return release_status_expiry(info.get("status"), upcoming_dates=upcoming)


async def fetch_movie_release_info(client, tmdb_id, tmdb_key, tmdb_status):
    cache_key=f"movie_{tmdb_id}"
    cached=get_cached_movie_release_info(cache_key)
    if cached and _release_info_is_current(cached):
        cached["status"]=_compute_movie_status(
            _parse(cached.get("theatrical_date")),
            _parse(cached.get("digital_date")),
            _parse(cached.get("physical_date")),
            tmdb_status,
            _parse(cached.get("premiere_date")),
        )
        return cached
    info={"status":None,"theatrical_date":None,"digital_date":None,"physical_date":None,"premiere_date":None}
    if tmdb_status in {"In Production","Post Production","Planned","Rumored"}:
        info["status"]="Production"; set_cached_movie_release_info(cache_key,info); return info
    if tmdb_status == "Cancelled":
        info["status"]="Cancelled"; set_cached_movie_release_info(cache_key,info); return info
    try:
        r=await client.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}/release_dates",params={"api_key":tmdb_key})
        r.raise_for_status(); payload=r.json()
    except Exception as exc:
        log.warning("TMDB release_dates failed for %s: %s",tmdb_id,exc); return None
    earliest_theatrical=earliest_digital=latest_digital=earliest_physical=earliest_premiere=None
    for entry in payload.get("results",[]):
        for rd in entry.get("release_dates",[]):
            d=_parse(rd.get("release_date")); typ=rd.get("type")
            if not d: continue
            if typ==5: earliest_physical=d if earliest_physical is None or d<earliest_physical else earliest_physical
            elif typ in (4,6):
                earliest_digital=d if earliest_digital is None or d<earliest_digital else earliest_digital
                latest_digital=d if latest_digital is None or d>latest_digital else latest_digital
            elif typ in (2,3):
                earliest_theatrical=d if earliest_theatrical is None or d<earliest_theatrical else earliest_theatrical
            elif typ == 1:
                earliest_premiere=d if earliest_premiere is None or d<earliest_premiere else earliest_premiere
    info={"status":_compute_movie_status(earliest_theatrical,earliest_digital,earliest_physical,tmdb_status,earliest_premiere),
          "theatrical_date":earliest_theatrical.isoformat() if earliest_theatrical else None,
          "digital_date":earliest_digital.isoformat() if earliest_digital else None,
          "physical_date":earliest_physical.isoformat() if earliest_physical else None,
          "digital_latest_date":latest_digital.isoformat() if latest_digital else None,
          "premiere_date":earliest_premiere.isoformat() if earliest_premiere else None}
    set_cached_movie_release_info(cache_key,info,_release_info_expiry(info))
    return info


async def fetch_recent_movie_digital_release_date(client, tmdb_id, tmdb_key, tmdb_status, max_age_days=14):
    info=await fetch_movie_release_info(client,tmdb_id,tmdb_key,tmdb_status)
    if not info: return None
    d=_parse(info.get("digital_latest_date") or info.get("digital_date"))
    if not d: return None
    age=(date.today()-d).days
    return d.isoformat() if 0<=age<=max_age_days else None


async def fetch_release_status(client, tmdb_id, tmdb_key, media_type, tmdb_status):
    key=f"{media_type}_{tmdb_id}"
    if media_type in ("tv","series"):
        mapping={"Returning Series":"Airing","In Production":"Production","Planned":"Production","Pilot":"Production","Ended":"Ended","Cancelled":"Cancelled","Canceled":"Cancelled"}
        result=mapping.get(tmdb_status or "")
        cached=get_cached_release_status(key)
        if not result: return cached
        if cached!=result: set_cached_release_status(key,result)
        return result
    cached=get_cached_release_status(key)
    if cached: return cached
    info=await fetch_movie_release_info(client,tmdb_id,tmdb_key,tmdb_status)
    result=(info or {}).get("status")
    if result: set_cached_release_status(key,result,_release_info_expiry(info))
    return result
