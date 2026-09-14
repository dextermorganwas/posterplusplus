from __future__ import annotations
import hashlib, logging
import httpx
from .config import settings
from .core.cache import FileCache

log=logging.getLogger(__name__)
MDBLIST_RE='https://mdblist.com/lists/'

class Trending:
    def __init__(self, cache: FileCache): self.cache=cache

    def source(self,media_type):
        return settings.trending_source_tv if media_type in {'tv','series'} else settings.trending_source_movie

    def normalize(self,url):
        if url.startswith(MDBLIST_RE):
            path=url[len(MDBLIST_RE):].split('?',1)[0].strip('/')
            if path.endswith('/json'): path=path[:-5].rstrip('/')
            return MDBLIST_RE+path+'/json'
        return url

    async def ranks(self, client:httpx.AsyncClient, media_type:str, tmdb_key:str)->dict[str,int]:
        key=f'{media_type}:{self.source(media_type) or "tmdb"}:{settings.trending_count}:{settings.trending_broad_count}'
        cached=self.cache.read_json('trending',key,settings.selection_cache_ttl_seconds)
        if cached: return {str(k):int(v) for k,v in cached.items()}
        url=self.source(media_type)
        if url:
            url=self.normalize(url)
            r=await client.get(url,follow_redirects=True)
            r.raise_for_status(); payload=r.json()
            if isinstance(payload,dict): items=payload.get('results') or [] ; ranked_by='position'
            else: items=payload if isinstance(payload,list) else []; ranked_by='rank'
            wanted='show' if media_type in {'tv','series'} else 'movie'
            out=[]; seen=set()
            for pos,row in enumerate(items):
                if not isinstance(row,dict): continue
                kind=str(row.get('mediatype') or row.get('media_type') or '').lower()
                if kind:
                    kind='show' if kind in {'tv','series'} else kind
                    if kind!=wanted: continue
                raw=row.get('id',row.get('tmdb_id',row.get('tmdbid')))
                if raw is None or not str(raw).isdigit(): continue
                tid=str(raw)
                if tid in seen: continue
                seen.add(tid); order=row.get('rank') if ranked_by=='rank' else pos
                out.append((float(order) if isinstance(order,(int,float)) else pos,tid))
            out.sort(key=lambda x:x[0]); ids=[x[1] for x in out]
        else:
            path='tv' if media_type in {'tv','series'} else 'movie'
            r=await client.get(f'https://api.themoviedb.org/3/trending/{path}/day',params={'api_key':tmdb_key},timeout=settings.http_timeout_seconds)
            r.raise_for_status(); ids=[str(x.get('id')) for x in (r.json().get('results') or []) if str(x.get('id','')).isdigit()]
        ranks={tid:i+1 for i,tid in enumerate(ids[:settings.trending_broad_count])}
        self.cache.write_json('trending',key,ranks)
        return ranks
