from __future__ import annotations
import asyncio, logging, re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from .config import settings
from .resolver import Resolver
from .core.state import init_db, stats as state_stats, prune_digital_releases, close_db
from .digital_release import digital_release_poll_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log=logging.getLogger("mediaart-router")
resolver=Resolver()

PATH_RE=re.compile(r"^tmdb:(?P<type>movie|series|tv):(?P<tmdb>[^&.]*?)(?:&imdb:(?P<imdb>[^&.]*?))?(?:&tvdb:(?P<tvdb>[^.]*?))?(?:\.(?P<ext>jpg|jpeg|png|webp))?$", re.I)

def auth_ok(request: Request) -> bool:
    if not settings.access_key: return True
    return request.headers.get("x-access-key")==settings.access_key or request.query_params.get("access_key")==settings.access_key

def parse_path(spec: str):
    m=PATH_RE.match(spec)
    if not m:return None
    return m.group("type"), m.group("tmdb") or None, m.group("imdb") or None, m.group("tvdb") or None, m.group("ext") or "jpg"

async def _background_maintenance(stop_event: asyncio.Event):
    try:
        # Keep the IMDb local dataset current even before the first poster request.
        if resolver.client:
            await resolver.toprated.refresh_if_needed(resolver.client)
        last_prune=0.0
        while not stop_event.is_set():
            now=asyncio.get_running_loop().time()
            if now-last_prune>3600:
                try: prune_digital_releases()
                except Exception: log.exception("Digital release prune failed")
                last_prune=now
            try: await asyncio.wait_for(stop_event.wait(), timeout=max(300, settings.top_rated_refresh_hours*3600))
            except asyncio.TimeoutError:
                if resolver.client:
                    await resolver.toprated.refresh_if_needed(resolver.client)
    except asyncio.CancelledError:
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); await resolver.start()
    resolver.stop_event=asyncio.Event()
    resolver.background_tasks=[
        asyncio.create_task(digital_release_poll_loop(resolver.client, resolver.stop_event)),
        asyncio.create_task(_background_maintenance(resolver.stop_event)),
    ]
    log.info("Media Art Router started on %s:%s",settings.host,settings.port)
    try:
        yield
    finally:
        await resolver.stop()
        close_db()
        log.info("Media Art Router shut down cleanly")

app=FastAPI(title="Media Art Router",version="1.0.0",lifespan=lifespan)

async def render(kind, request: Request, tmdb_id=None, imdb_id=None, tvdb_id=None, media_type=None, lang="en", ext="jpg", with_sash=False):
    if not auth_ok(request): raise HTTPException(401,"Unauthorized")
    media_type=media_type or "movie"
    try:
        raw,provider,sash=await resolver.select_art(kind,media_type,tmdb_id,imdb_id,tvdb_id,lang,with_sash)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except HTTPException: raise
    except Exception as exc:
        log.exception("art request failed")
        raise HTTPException(502, f"Unable to resolve artwork: {exc}")
    media="image/png" if kind=="logo" and raw.startswith(b"\x89PNG") else "image/jpeg" if raw.startswith(b"\xff\xd8") else "application/octet-stream"
    headers={"X-Art-Provider":provider,"X-Sash":sash or "","Cache-Control":"public, max-age=86400"}
    return Response(content=raw,media_type=media,headers=headers)

@app.get("/health")
async def health(): return {"ok":True,"port":settings.port}

@app.get("/backdrop/{spec}")
async def backdrop_spec(spec: str, request: Request):
    p=parse_path(spec)
    if not p: raise HTTPException(400,"Invalid artwork spec")
    return await render("backdrop",request,p[1],p[2],p[3],p[0],"en",p[4],False)

@app.get("/poster/{spec}")
async def poster_spec(spec: str, request: Request):
    p=parse_path(spec)
    if not p: raise HTTPException(400,"Invalid artwork spec")
    return await render("poster",request,p[1],p[2],p[3],p[0],"en",p[4],True)

@app.get("/logo/{spec}")
async def logo_spec(spec: str, request: Request):
    p=parse_path(spec)
    if not p: raise HTTPException(400,"Invalid artwork spec")
    return await render("logo",request,p[1],p[2],p[3],p[0],"en",p[4],False)

@app.get("/poster")
async def poster_query(request: Request, tmdb_id: str|None=None, imdb_id: str|None=None, tvdb_id: str|None=None, type: str="movie", lang: str="en"):
    return await render("poster",request,tmdb_id,imdb_id,tvdb_id,type,lang,"jpg",True)

@app.get("/backdrop")
async def backdrop_query(request: Request, tmdb_id: str|None=None, imdb_id: str|None=None, tvdb_id: str|None=None, type: str="movie", lang: str="en"):
    return await render("backdrop",request,tmdb_id,imdb_id,tvdb_id,type,lang,"jpg",False)

@app.get("/logo")
async def logo_query(request: Request, tmdb_id: str|None=None, imdb_id: str|None=None, tvdb_id: str|None=None, type: str="movie", lang: str="en"):
    return await render("logo",request,tmdb_id,imdb_id,tvdb_id,type,lang,"png",False)

@app.get("/stats")
async def stats(request: Request):
    if not auth_ok(request): raise HTTPException(401,"Unauthorized")
    return {
        "inflight": len(resolver.inflight),
        "top_rated_count": len(resolver.toprated.ratings),
        "port": settings.port,
        "sash_priority": list(settings.sash_priority),
        "state": state_stats(),
    }

@app.get("/debug/sash")
async def debug_sash(request: Request, tmdb_id: str|None=None, imdb_id: str|None=None, tvdb_id: str|None=None, type: str="movie", lang: str="en"):
    if not auth_ok(request): raise HTTPException(401,"Unauthorized")
    if not tmdb_id and not imdb_id and not tvdb_id: raise HTTPException(400,"Provide tmdb_id, imdb_id, or tvdb_id")
    # The regular artwork response remains the source of truth; this endpoint simply
    # calls it so operators can inspect the selected provider and sash headers without
    # downloading another display in a client.
    response=await render("poster",request,tmdb_id,imdb_id,tvdb_id,type,lang,"jpg",True)
    return {"art_provider":response.headers.get("X-Art-Provider"),"sash":response.headers.get("X-Sash") or None,"content_type":response.media_type}

@app.exception_handler(Exception)
async def general_error(request, exc):
    log.exception("Unhandled request failure")
    return JSONResponse({"error":"internal_error","detail":"Artwork resolution failed"},status_code=502)
