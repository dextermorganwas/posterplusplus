from __future__ import annotations
from typing import Any
import httpx
BASE="https://api.themoviedb.org/3"; IMG="https://image.tmdb.org/t/p"

def endpoint(media_type): return "tv" if media_type in {"tv","series"} else "movie"

async def get_details(client,key,media_type,tmdb_id):
    r=await client.get(f"{BASE}/{endpoint(media_type)}/{tmdb_id}",params={"api_key":key,"append_to_response":"images,credits,external_ids,keywords","include_image_language":"en,null"}); r.raise_for_status(); return r.json()
async def get_images(client,key,media_type,tmdb_id,languages):
    langs=[x for x in languages if x]
    vals=[]
    for x in langs+["en"]:
        if x not in vals: vals.append(x)
    vals.append("null") if "null" not in vals else None
    r=await client.get(f"{BASE}/{endpoint(media_type)}/{tmdb_id}/images",params={"api_key":key,"include_image_language":",".join(vals)}); r.raise_for_status(); return r.json()
async def find_by_imdb(client,key,imdb_id,media_type_hint=None):
    r=await client.get(f"{BASE}/find/{imdb_id}",params={"api_key":key,"external_source":"imdb_id"}); r.raise_for_status(); d=r.json()
    movies=d.get("movie_results") or []; tv=d.get("tv_results") or []
    if media_type_hint in ("tv","series") and tv: return str(tv[0]["id"]),"tv"
    if media_type_hint=="movie" and movies: return str(movies[0]["id"]),"movie"
    if movies: return str(movies[0]["id"]),"movie"
    if tv: return str(tv[0]["id"]),"tv"
    return None

def image_url(kind,path,settings):
    size=settings.tmdb_poster_size if kind=="poster" else settings.tmdb_backdrop_size if kind=="backdrop" else settings.tmdb_logo_size
    return f"{IMG}/{size}/{path.lstrip('/') }"

def lang_code(item):
    x=item.get("iso_639_1"); return None if x in (None,"") else x

def pick(items,wanted,textless=False):
    candidates=[x for x in items if (not textless or lang_code(x) is None)]
    for want in wanted:
        xs=[x for x in candidates if lang_code(x)==want]
        if xs: return max(xs,key=lambda x:(x.get("vote_average") or 0,x.get("vote_count") or 0))
    if textless: return max(candidates,key=lambda x:(x.get("vote_average") or 0,x.get("vote_count") or 0)) if candidates else None
    neutral=[x for x in candidates if lang_code(x) is None]
    if neutral: return max(neutral,key=lambda x:(x.get("vote_average") or 0,x.get("vote_count") or 0))
    return None

def primary(details,kind):
    return details.get("poster_path") if kind=="poster" else details.get("backdrop_path") if kind=="backdrop" else None
