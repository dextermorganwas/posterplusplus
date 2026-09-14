from __future__ import annotations
import asyncio, hashlib, logging, re, time
import httpx
from .config import settings
from .core.cache import FileCache
log=logging.getLogger(__name__)
_RE=re.compile(r"^https?://(?:www\.)?mdblist\.com/lists/(?P<path>[^\s?#]+)",re.I)
_failed={}; _inflight={}
class Trending:
    def __init__(self,cache): self.cache=cache
    def source(self,media_type): return settings.trending_source_tv if media_type in {"tv","series"} else settings.trending_source_movie
    def normalize(self,url):
        m=_RE.match(url.strip())
        if not m:return url.strip()
        path=m.group('path').strip('/')
        if path.endswith('/json'):path=path[:-5].rstrip('/')
        return f"https://mdblist.com/lists/{path}/json" if path else url.strip()
    def signature(self,media_type):
        u=self.normalize(self.source(media_type)); return "tmdb" if not u else "url:"+hashlib.sha256(u.encode()).hexdigest()[:16]
    async def _source_ids(self,client,media_type):
        url=self.source(media_type)
        if not url:return None
        shown=self.normalize(url)
        fail=_failed.get(media_type)
        if fail and time.monotonic()-fail<settings.trending_source_retry_seconds:return []
        try:
            r=await client.get(shown,follow_redirects=True,timeout=settings.http_timeout_seconds); r.raise_for_status(); payload=r.json()
        except Exception as exc:
            _failed[media_type]=time.monotonic(); log.warning('Trending source failed for %s (%s): %s',media_type,shown,exc); return []
        items=payload.get('results') if isinstance(payload,dict) else payload
        if not isinstance(items,list): _failed[media_type]=time.monotonic(); return []
        wanted='show' if media_type in {'tv','series'} else 'movie'; rows=[]
        for pos,row in enumerate(items):
            if not isinstance(row,dict):continue
            kind=str(row.get('mediatype') or row.get('media_type') or '').lower()
            if kind in {'tv','series'}:kind='show'
            if kind and kind!=wanted:continue
            raw=row.get('id',row.get('tmdb_id',row.get('tmdbid')))
            if raw is None or not str(raw).isdigit():continue
            order=row.get('rank') if isinstance(payload,list) else pos
            rows.append((float(order) if isinstance(order,(int,float)) else pos,str(raw)))
        rows.sort(key=lambda x:x[0]); out=[]; seen=set()
        for _,tid in rows:
            if tid not in seen:seen.add(tid);out.append(tid)
            if len(out)>=settings.trending_source_max_items:break
        if not out:_failed[media_type]=time.monotonic(); return []
        _failed.pop(media_type,None); return out
    async def ranks(self,client,media_type,tmdb_key):
        endpoint='tv' if media_type in {'tv','series'} else 'movie'; sig=self.signature(endpoint)
        key=f'{endpoint}:{sig}:{settings.trending_count}:{settings.trending_broad_count}'
        cached=self.cache.read_json('trending',key,settings.selection_cache_ttl_seconds)
        if cached:return {str(k):int(v) for k,v in cached.items()}
        event=_inflight.get(endpoint)
        if event:
            await event.wait(); cached=self.cache.read_json('trending',key,settings.selection_cache_ttl_seconds)
            if cached:return {str(k):int(v) for k,v in cached.items()}
        event=asyncio.Event(); _inflight[endpoint]=event
        try:
            source_ids=await self._source_ids(client,endpoint)
            if source_ids is not None:
                if not source_ids:return {}
                ids=source_ids
            else:
                async def page(p):
                    r=await client.get(f"https://api.themoviedb.org/3/trending/{endpoint}/day",params={"api_key":tmdb_key,"page":p},timeout=settings.http_timeout_seconds); r.raise_for_status(); return r.json().get('results',[])
                pages=await asyncio.gather(*(page(p) for p in range(1,6)))
                ids=[str(x['id']) for results in pages for x in results if str(x.get('id','')).isdigit()]
            rankings={tid:i+1 for i,tid in enumerate(ids[:settings.trending_broad_count])}; self.cache.write_json('trending',key,rankings); return rankings
        finally:
            event.set(); _inflight.pop(endpoint,None)
