from __future__ import annotations
import json, sqlite3, threading, time
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path

from app.config import settings

_LOCK = threading.RLock()
_CONN = None

_RELEASE_TTL_DAYS = {
    "Physical": 90, "Cancelled": 90, "Ended": 60,
    "Streaming": 30, "Cinema": 1, "Production": 1,
    "Airing": 3, "Returning": 3,
}
_FALLBACK_DAYS = 7
_BOUNDARY_MAX_DAYS = 14


def _db_path() -> str:
    return str(Path(settings.cache_dir) / "state.db")


def init_db() -> None:
    global _CONN
    Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
    with _LOCK:
        if _CONN is None:
            _CONN = sqlite3.connect(_db_path(), check_same_thread=False)
            _CONN.execute("PRAGMA journal_mode=WAL")
            _CONN.execute("PRAGMA busy_timeout=15000")
            _CONN.execute("PRAGMA synchronous=NORMAL")
        db = _CONN
        db.executescript("""
        CREATE TABLE IF NOT EXISTS digital_release_cache (
            imdb_id TEXT PRIMARY KEY,
            posted_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS release_status_cache (
            cache_key TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            cached_at INTEGER NOT NULL,
            expires_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS movie_release_info_cache (
            cache_key TEXT PRIMARY KEY,
            info_json TEXT NOT NULL,
            cached_at INTEGER NOT NULL,
            expires_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        db.commit()


def _db():
    if _CONN is None:
        init_db()
    return _CONN


def is_digital_release(imdb_id: str | None) -> bool:
    if not imdb_id:
        return False
    with _LOCK:
        return _db().execute("SELECT 1 FROM digital_release_cache WHERE imdb_id=?", (imdb_id,)).fetchone() is not None


def add_digital_releases(entries: list[tuple[str, int]]) -> int:
    if not entries:
        return 0
    with _LOCK:
        db = _db(); inserted = 0
        for imdb_id, posted_at in entries:
            cur = db.execute("INSERT OR IGNORE INTO digital_release_cache(imdb_id,posted_at) VALUES(?,?)", (imdb_id, posted_at))
            inserted += cur.rowcount
        db.commit(); return inserted


def prune_digital_releases() -> int:
    cutoff = int(time.time()) - settings.digital_release_max_age_days * 86400
    with _LOCK:
        cur = _db().execute("DELETE FROM digital_release_cache WHERE posted_at < ?", (cutoff,)); _db().commit(); return cur.rowcount


def release_status_ttl_seconds(status: str | None) -> int:
    return _RELEASE_TTL_DAYS.get(status or "", _FALLBACK_DAYS) * 86400


def _release_row_expiry(status: str | None, cached_at: int) -> int:
    return cached_at + release_status_ttl_seconds(status)


def release_status_expiry(status: str | None, *, upcoming_dates: list[int] | None = None, now: int | None = None) -> int:
    now = int(time.time() if now is None else now)
    future = sorted(int(x) for x in (upcoming_dates or []) if int(x) > now)
    if future:
        deadline = min(future[0], now + _BOUNDARY_MAX_DAYS * 86400)
    else:
        deadline = _release_row_expiry(status, now)
    return max(deadline, now + 3600)


def get_cached_release_status(cache_key: str) -> str | None:
    with _LOCK:
        row = _db().execute("SELECT status,cached_at,expires_at FROM release_status_cache WHERE cache_key=?", (cache_key,)).fetchone()
    if not row: return None
    status, cached_at, expires_at = row
    if time.time() > (expires_at or _release_row_expiry(status, cached_at)):
        return None
    return status


def set_cached_release_status(cache_key: str, status: str, expires_at: int | None = None) -> None:
    now = int(time.time())
    exp = int(expires_at or _release_row_expiry(status, now))
    with _LOCK:
        _db().execute("""INSERT INTO release_status_cache(cache_key,status,cached_at,expires_at)
        VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET status=excluded.status,cached_at=excluded.cached_at,expires_at=excluded.expires_at""", (cache_key,status,now,exp)); _db().commit()


def get_cached_movie_release_info(cache_key: str) -> dict | None:
    with _LOCK:
        row = _db().execute("SELECT info_json,cached_at,expires_at FROM movie_release_info_cache WHERE cache_key=?", (cache_key,)).fetchone()
    if not row: return None
    raw, cached_at, expires_at = row
    try: info = json.loads(raw)
    except Exception: return None
    if time.time() > (expires_at or _release_row_expiry(info.get("status"), cached_at)):
        return None
    return info


def set_cached_movie_release_info(cache_key: str, info: dict, expires_at: int | None = None) -> None:
    now = int(time.time())
    exp = int(expires_at or _release_row_expiry(info.get("status"), now))
    with _LOCK:
        _db().execute("""INSERT INTO movie_release_info_cache(cache_key,info_json,cached_at,expires_at)
        VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET info_json=excluded.info_json,cached_at=excluded.cached_at,expires_at=excluded.expires_at""", (cache_key,json.dumps(info),now,exp)); _db().commit()


def claim_job(key: str, min_interval: float) -> bool:
    now = time.time()
    with _LOCK:
        db = _db()
        row = db.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
        if row:
            try:
                if now - float(row[0]) < min_interval:
                    return False
            except (TypeError, ValueError):
                pass
        db.execute("INSERT INTO app_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,str(now)))
        db.commit(); return True


def stats() -> dict:
    with _LOCK:
        db = _db()
        out={}
        for table in ("digital_release_cache","release_status_cache","movie_release_info_cache"):
            out[table]=db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        try: out["db_file_bytes"]=Path(_db_path()).stat().st_size
        except OSError: out["db_file_bytes"]=None
        return out


def close_db() -> None:
    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close(); _CONN=None
