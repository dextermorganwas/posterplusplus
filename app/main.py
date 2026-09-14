from __future__ import annotations
import io, logging, re, signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from .config import settings
from .resolver import Resolver

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log=logging.getLogger('mediaart-router')
resolver=Resolver()

PATH_RE=re.compile(r"^tmdb:(?P<type>movie|series|tv):(?P<tmdb>[^&]*?)(?:&imdb:(?P<imdb>[^&]*?))?(?:&tvdb:(?P<tvdb>[^.]*?))?(?:\.(?P<ext>jpg|jpeg|png|webp))?$",re.I)


def auth_ok(request:Request)->bool:
    if not settings.access_key: return True
    return request.headers.get('x-access-key')==settings.access_key or request.query_params.get('access_key')==settings.access_key


def parse_path(spec:str,kind:str):
    m=PATH_RE.match(spec)
    if m: return m.group('type'), m.group('tmdb') or None, m.group('imdb') or None, m.group('tvdb') or None, m.group('ext') or 'jpg'
    # query-param compatible endpoint
    return None

async def render(kind, request:Request, tmdb_id:str|None=None, imdb_id:str|None=None, tvdb_id:str|None=None, media_type:str|None=None, lang:str='en', with_sash=False):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    if not tmdb_id: raise HTTPException(400,'tmdb_id required')
    media_type=media_type or 'movie'
    raw,provider,sash=await resolver.select_art(kind,media_type,tmdb_id,imdb_id,tvdb_id,lang,with_sash)
    media='image/jpeg'
    if kind=='logo': media='image/png'
    return Response(content=raw,media_type=media,headers={'X-Art-Provider':provider,'X-Sash':sash or ''})

@asynccontextmanager
async def lifespan(app):
    log.info('starting media-art router')
    yield
    log.info('graceful shutdown complete')

app=FastAPI(title='Media Art Router',version='0.1.0',lifespan=lifespan)

@app.get('/health')
async def health(): return {'ok':True}

@app.get('/backdrop/{spec}')
async def backdrop_spec(spec:str,request:Request):
    p=parse_path(spec,'backdrop')
    if not p: raise HTTPException(400,'Invalid backdrop spec')
    return await render('backdrop',request,*p[:4],lang='en',with_sash=False)

@app.get('/poster/{spec}')
async def poster_spec(spec:str,request:Request):
    p=parse_path(spec,'poster')
    if not p: raise HTTPException(400,'Invalid poster spec')
    return await render('poster',request,*p[:4],lang='en',with_sash=True)

@app.get('/logo/{spec}')
async def logo_spec(spec:str,request:Request):
    p=parse_path(spec,'logo')
    if not p: raise HTTPException(400,'Invalid logo spec')
    return await render('logo',request,*p[:4],lang='en',with_sash=False)

@app.get('/poster')
async def poster_query(request:Request, tmdb_id:str|None=None, imdb_id:str|None=None, tvdb_id:str|None=None, type:str='movie', lang:str='en'):
    return await render('poster',request,tmdb_id,imdb_id,tvdb_id,type,lang,True)

@app.get('/backdrop')
async def backdrop_query(request:Request, tmdb_id:str|None=None, imdb_id:str|None=None, tvdb_id:str|None=None, type:str='movie', lang:str='en'):
    return await render('backdrop',request,tmdb_id,imdb_id,tvdb_id,type,lang,False)

@app.get('/logo')
async def logo_query(request:Request, tmdb_id:str|None=None, imdb_id:str|None=None, tvdb_id:str|None=None, type:str='movie', lang:str='en'):
    return await render('logo',request,tmdb_id,imdb_id,tvdb_id,type,lang,False)

@app.get('/stats')
async def stats(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    return {'inflight':len(resolver.inflight),'top_rated_count':len(resolver.toprated.ratings)}

@app.exception_handler(Exception)
async def general_error(request, exc):
    log.exception('request failed')
    return JSONResponse({'error':'internal_error','detail':str(exc)},status_code=502)
