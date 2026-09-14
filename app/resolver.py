from __future__ import annotations
import asyncio, io, logging
from typing import Any
import httpx
from PIL import Image
from .config import settings
from .core.cache import FileCache
from .core.color import dominant_sash_color
from .core.discovery_adapter import build_discovery, pick_sash_with_top_rated
from .core.sash import draw_status_sash
from .providers import tmdb
from .providers.tvdb import TVDBClient
from .providers.metahub import fetch as metahub_fetch
from .toprated import IMDbRatings
from .trending import Trending

log=logging.getLogger(__name__)

class Resolver:
    def __init__(self):
        self.cache=FileCache(settings.cache_dir)
        self.inflight: dict[str, asyncio.Task] = {}
        self.guard=asyncio.Lock()
        self.toprated=IMDbRatings(f"{settings.cache_dir}/title.ratings.tsv.gz",settings.top_rated_refresh_hours,settings.top_rated_min_votes)
        self.trending=Trending(self.cache)

    async def coalesced(self,key, coro_factory):
        async with self.guard:
            task=self.inflight.get(key)
            if task is None or task.done():
                task=asyncio.create_task(coro_factory()); self.inflight[key]=task
        try: return await task
        finally:
            async with self.guard:
                if self.inflight.get(key) is task: self.inflight.pop(key,None)

    def lang_order(self, requested:str|None, original:str|None)->list[str]:
        out=[]
        for x in (requested or 'en', 'en', original):
            if x and x not in out: out.append(x)
        return out

    async def _tvdb_selection(self, client, media_type, kind, tvdb_id, imdb_id, tmdb_id, requested, original, bypass_count=False):
        if not settings.tvdb_api_key: return None
        tv=TVDBClient(client,settings.tvdb_api_key,settings.tvdb_pin)
        tid=await tv.resolve_id(media_type,tvdb_id=tvdb_id,imdb_id=imdb_id,tmdb_id=tmdb_id)
        if not tid: return None
        arts=await tv.artworks(media_type,tid)
        type_map=await tv.artwork_type_map(media_type)
        wanted_cat={'poster':'posters','backdrop':'backgrounds','logo':'logos'}[kind]
        cat=[a for a in arts if type_map.get(a.get('type'))==wanted_cat]
        threshold=settings.tvdb_min_logos if kind=='logo' else settings.tvdb_min_artworks
        if not bypass_count and len(cat)<threshold: return None
        order=self.lang_order(requested,original)
        mp={'en':'eng','es':'spa','fr':'fra','de':'deu','it':'ita','pt':'por','ja':'jpn','ko':'kor','zh':'zho','ru':'rus','nl':'nld','pl':'pol','sv':'swe','da':'dan','no':'nor','fi':'fin','tr':'tur','ar':'ara','hi':'hin','cs':'ces','hu':'hun','el':'ell','he':'heb','th':'tha','uk':'ukr','ro':'ron'}
        order3=[mp.get(x,x) for x in order]
        def lang(a): return str(a.get('language') or '').lower()
        def score(a): return (float(a.get('score') or 0), float(a.get('vote_average') or 0))
        chosen=None
        for want in order3:
            xs=[a for a in cat if lang(a)==want]
            if xs: chosen=max(xs,key=score); break
        if chosen is None:
            neutral=[a for a in cat if not lang(a)]
            if neutral: chosen=max(neutral,key=score)
        if chosen is None and kind!='logo' and cat:
            chosen=max(cat,key=score)
        if chosen is None: return None
        url=chosen.get('image') or ''
        return url if url.startswith('http') else 'https://artworks.thetvdb.com/'+url.lstrip('/')

    async def select_art(self, kind, media_type, tmdb_id, imdb_id=None, tvdb_id=None, lang='en', with_sash=False):
        key=f"{kind}:{media_type}:{tmdb_id}:{imdb_id}:{tvdb_id}:{lang}:{with_sash}:{','.join(settings.sash_priority)}"
        return await self.coalesced(key, lambda: self._select_art_uncached(kind,media_type,tmdb_id,imdb_id,tvdb_id,lang,with_sash))

    async def _select_art_uncached(self,kind,media_type,tmdb_id,imdb_id,tvdb_id,lang,with_sash):
        if not settings.tmdb_api_key: raise RuntimeError('TMDB_API_KEY is required')
        timeout=httpx.Timeout(settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers={'User-Agent':'MediaArtRouter/1.0'}) as client:
            metadata_key=f'{media_type}:{tmdb_id}:{lang}'
            cached_meta=self.cache.read_json('metadata',metadata_key,settings.metadata_cache_ttl_seconds)
            details=cached_meta or await tmdb.get_details(client,settings.tmdb_api_key,media_type,str(tmdb_id))
            if not cached_meta: self.cache.write_json('metadata',metadata_key,details)
            original=details.get('original_language')
            order=self.lang_order(lang,original)
            imgs=details.get('images') or {}
            if original and original not in {'en', lang, 'en-US'}:
                imgs2=await tmdb.get_images(client,settings.tmdb_api_key,media_type,str(tmdb_id),order+[original])
                for k,v in imgs2.items():
                    if isinstance(v,list): imgs.setdefault(k,[]); imgs[k].extend(v)
            selected=None; provider='tmdb'
            if kind=='poster': selected=tmdb.pick(imgs.get('posters',[]),wanted=order,textless=False)
            elif kind=='logo': selected=tmdb.pick(imgs.get('logos',[]),wanted=order,textless=False)
            elif kind=='backdrop': selected=tmdb.pick(imgs.get('backdrops',[]),wanted=order,textless=settings.textless_backdrops_only)
            # Build explicit TVDB-first choice; if TVDB meets threshold it wins.
            tvdb_url=await self._tvdb_selection(client,media_type,kind,tvdb_id,imdb_id,str(tmdb_id),lang,original,False)
            if tvdb_url:
                selected_url=tvdb_url; provider='tvdb'
            elif selected and selected.get('file_path'):
                selected_url=tmdb.image_url(kind,selected['file_path'],settings)
            else:
                raw=await metahub_fetch(client,kind,imdb_id) if imdb_id else None
                if raw:
                    return await self._finish_bytes(raw,kind,details,media_type,tmdb_id,imdb_id,provider='metahub',client=client,with_sash=with_sash)
                # Last resort: relax TVDB count threshold, but keep language preference.
                tvdb_url=await self._tvdb_selection(client,media_type,kind,tvdb_id,imdb_id,str(tmdb_id),lang,original,True)
                if tvdb_url:
                    selected_url=tvdb_url; provider='tvdb-fallback'
                else:
                    p=tmdb.primary(details,kind)
                    if p:
                        selected_url=tmdb.image_url(kind,p,settings); provider='tmdb-primary'
                    else:
                        raise httpx.HTTPStatusError('No usable artwork',request=httpx.Request('GET','http://localhost'),response=httpx.Response(404))
            art_key=selected_url
            raw_cached=self.cache.read('art',art_key,'bin',settings.art_cache_ttl_seconds)
            if raw_cached is None:
                r=await client.get(selected_url,follow_redirects=True)
                r.raise_for_status(); raw_cached=r.content; self.cache.write_atomic('art',art_key,'bin',raw_cached)
            return await self._finish_bytes(raw_cached,kind,details,media_type,tmdb_id,imdb_id,provider,client,with_sash)

    async def _finish_bytes(self,raw,kind,details,media_type,tmdb_id,imdb_id,provider,client,with_sash):
        if kind!='poster' or not with_sash or not settings.enable_sashes:
            return raw, provider, None
        img=Image.open(io.BytesIO(raw)).convert('RGB')
        # Top-rated is refreshed independently and only meaningful with IMDb identity.
        await self.toprated.refresh_if_needed(client)
        top=self.toprated.is_top(imdb_id)
        try:
            keywords=(details.get('keywords') or {}).get('keywords' if media_type=='movie' else 'results') or []
            if settings.mdblist_api_key:
                provider = 'imdb' if imdb_id else 'tmdb'
                media = 'show' if media_type in {'tv','series'} else 'movie'
                mid = imdb_id or str(tmdb_id)
                try:
                    mr=await client.get(f'https://api.mdblist.com/{provider}/{media}/{mid}',params={'apikey':settings.mdblist_api_key,'append_to_response':'keyword'})
                    if mr.status_code==200:
                        keywords = mr.json().get('keywords') or keywords
                except Exception as exc:
                    log.warning('MDBList enrichment failed for %s: %s',mid,exc)
        except Exception: keywords=[]
        tmdb_data={
          'original_language':details.get('original_language'),'production_companies':details.get('production_companies',[]),
          'credits':details.get('credits',{}),'runtime':details.get('runtime'), 'number_of_seasons':details.get('number_of_seasons'),
          'number_of_episodes':details.get('number_of_episodes'),'tmdb_status':details.get('status'),
          'tmdb_release_date':details.get('release_date') or details.get('first_air_date'),'next_episode':details.get('next_episode_to_air'),
          'last_episode':details.get('last_episode_to_air'),'seasons':details.get('seasons') or [],
        }
        try:
            ranks=await self.trending.ranks(client,media_type,settings.tmdb_api_key)
            trend_rank=ranks.get(str(tmdb_id))
        except Exception as exc:
            log.warning('Trending refresh failed: %s',exc); trend_rank=None
        meta=build_discovery(tmdb_data=tmdb_data,media_type=media_type,tmdb_id=tmdb_id,keywords=keywords,trending_rank=trend_rank,top_rated=top,settings=settings)
        picked=pick_sash_with_top_rated(meta,list(settings.sash_priority))
        if picked:
            label, _stype=picked
            c,t=dominant_sash_color(img,settings.sash_dark_threshold,settings.sash_force_gray_on_dark)
            img=draw_status_sash(img,label,c,t,settings)
            out=io.BytesIO(); img.save(out,format='JPEG',quality=92); return out.getvalue(),provider,label
        return raw,provider,None
