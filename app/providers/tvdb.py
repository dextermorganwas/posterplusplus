from __future__ import annotations
import asyncio
import httpx
BASE="https://api4.thetvdb.com/v4"; ART_BASE="https://artworks.thetvdb.com"
class TVDBClient:
    def __init__(self,client,key,pin=""): self.client,self.key,self.pin=client,key,pin; self._token=None; self._lock=asyncio.Lock()
    async def token(self):
        if self._token:return self._token
        async with self._lock:
            if self._token:return self._token
            body={"apikey":self.key};
            if self.pin: body["pin"]=self.pin
            r=await self.client.post(f"{BASE}/login",json=body); r.raise_for_status(); self._token=r.json()["data"]["token"]; return self._token
    async def get(self,path,**params):
        tok=await self.token(); r=await self.client.get(f"{BASE}{path}",params=params or None,headers={"Authorization":f"Bearer {tok}"})
        if r.status_code==401:
            self._token=None; tok=await self.token(); r=await self.client.get(f"{BASE}{path}",params=params or None,headers={"Authorization":f"Bearer {tok}"})
        r.raise_for_status(); return r.json().get("data")
    async def resolve_id(self,media_type,tvdb_id=None,imdb_id=None,tmdb_id=None):
        if tvdb_id and str(tvdb_id).isdigit(): return int(tvdb_id)
        want="series" if media_type in {"tv","series"} else "movie"
        for remote in (imdb_id,tmdb_id):
            if not remote: continue
            try:data=await self.get(f"/search/remoteid/{remote}")
            except Exception: continue
            if isinstance(data,list):
                for row in data:
                    rec=row.get(want) if isinstance(row,dict) else None
                    if isinstance(rec,dict) and rec.get("id"): return int(rec["id"])
        return None
    async def extended(self,media_type,tvdb_id):
        root="series" if media_type in {"tv","series"} else "movies"; return await self.get(f"/{root}/{tvdb_id}/extended",short="false")
    async def artworks(self,media_type,tvdb_id): return (await self.extended(media_type,tvdb_id) or {}).get("artworks") or []
    async def artwork_type_map(self):
        rows=await self.get("/artwork/types"); out={}
        for row in rows or []:
            rec=str(row.get("recordType") or "").lower()
            text=f"{row.get('slug') or ''} {row.get('name') or ''}".lower(); cat=None
            if "clearlogo" in text or text.strip().endswith("logo") or " logo" in text: cat="logos"
            elif "background" in text or "fanart" in text: cat="backdrops"
            elif "poster" in text: cat="posters"
            if cat and row.get("id"): out[int(row["id"])]=cat
        return out

def lang_norm(code):
    mp={"eng":"en","spa":"es","fra":"fr","deu":"de","ita":"it","por":"pt","jpn":"ja","kor":"ko","zho":"zh","rus":"ru","nld":"nl","pol":"pl","swe":"sv","dan":"da","nor":"no","fin":"fi","tur":"tr","ara":"ar","hin":"hi","ces":"cs","hun":"hu","ell":"el","heb":"he","tha":"th","ukr":"uk","ron":"ro"}
    return mp.get(str(code or '').lower(),str(code or '').lower()) or None
