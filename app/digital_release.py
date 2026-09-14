from __future__ import annotations
import asyncio, logging, re, time
import httpx
from app.config import settings
from app.core.state import add_digital_releases
log=logging.getLogger(__name__)
_URL="https://arctic-shift.photon-reddit.com/api/posts/search"
_RE=re.compile(r"tt\d{1,10}(?!\d)")
_LIMIT=100; _MAX_PAGES=10; _POLL=86400; _PAUSE=1.0

async def _fetch_page(client, after_ts, before_ts):
    try:
        r=await client.get(_URL,params={"subreddit":"movieleaks","after":after_ts,"before":before_ts,"limit":_LIMIT},timeout=15)
        r.raise_for_status(); return r.json().get("data",[])
    except Exception as exc:
        log.warning("Digital release: Arctic Shift fetch failed: %s",exc); return []

async def sync_digital_releases(client):
    now=int(time.time()); before=now-settings.digital_release_min_age_days*86400; after=now-settings.digital_release_max_age_days*86400
    entries=[]; cursor=before
    for page in range(_MAX_PAGES):
        posts=await _fetch_page(client,after,cursor)
        if not posts: break
        for post in posts:
            created=post.get("created_utc")
            if not created: continue
            hay=" ".join((post.get("selftext","") or "",post.get("title","") or "",post.get("url","") or ""))
            entries.extend((iid,int(created)) for iid in set(_RE.findall(hay)))
        if len(posts)<_LIMIT: break
        cursor=int(posts[-1].get("created_utc",cursor))-1
        if page<_MAX_PAGES-1: await asyncio.sleep(_PAUSE)
    return add_digital_releases(entries)

async def digital_release_poll_loop(client, stop_event: asyncio.Event):
    try:
        await asyncio.sleep(2)
        while not stop_event.is_set():
            try: await sync_digital_releases(client)
            except Exception as exc: log.exception("Digital release loop error: %s",exc)
            try: await asyncio.wait_for(stop_event.wait(), timeout=_POLL)
            except asyncio.TimeoutError: pass
    except asyncio.CancelledError:
        raise
