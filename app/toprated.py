from __future__ import annotations
import asyncio,gzip,logging,os,time
from pathlib import Path
import httpx
log=logging.getLogger(__name__)
URL="https://datasets.imdbws.com/title.ratings.tsv.gz"
class IMDbRatings:
    def __init__(self,path,refresh_hours,min_votes=500,threshold=8.5):
        self.path=Path(path); self.refresh_hours=refresh_hours; self.min_votes=min_votes; self.threshold=threshold; self.ratings={}; self.lock=asyncio.Lock()
        if self.path.exists():
            try:self._load()
            except Exception: self.ratings={}
    async def refresh_if_needed(self,client):
        if self.path.exists() and time.time()-self.path.stat().st_mtime < self.refresh_hours*3600:return
        async with self.lock:
            if self.path.exists() and time.time()-self.path.stat().st_mtime < self.refresh_hours*3600:return
            self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp.gz')
            try:
                r=await client.get(URL,timeout=180); r.raise_for_status(); tmp.write_bytes(r.content); os.replace(tmp,self.path); await asyncio.to_thread(self._load)
            except Exception as exc:
                log.warning('IMDb ratings refresh failed: %s',exc)
                try:tmp.unlink(missing_ok=True)
                except Exception:pass
    def _load(self):
        ratings={}
        with gzip.open(self.path,'rt',encoding='utf-8') as f:
            next(f,None)
            for line in f:
                p=line.rstrip('\n').split('\t')
                if len(p)<3:continue
                try:r=float(p[1]); votes=int(p[2])
                except ValueError:continue
                if r>=self.threshold and votes>=self.min_votes:ratings[p[0]]=r
        self.ratings=ratings
    def is_top(self,imdb_id):return bool(imdb_id and imdb_id in self.ratings)
