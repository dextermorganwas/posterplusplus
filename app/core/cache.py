from __future__ import annotations
import asyncio, hashlib, json, os, time
from pathlib import Path

class FileCache:
    def __init__(self, root: str):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.locks: dict[str, asyncio.Lock] = {}
        self.guard=asyncio.Lock()

    async def lock_for(self,key:str):
        async with self.guard:
            return self.locks.setdefault(key, asyncio.Lock())

    def path(self, namespace,key,ext):
        h=hashlib.sha256(key.encode()).hexdigest()
        p=self.root/namespace; p.mkdir(exist_ok=True)
        return p/f"{h}.{ext}"

    def fresh(self,p:Path,ttl:int)->bool:
        return p.exists() and (time.time()-p.stat().st_mtime)<ttl

    def read(self,namespace,key,ext,ttl):
        p=self.path(namespace,key,ext)
        if self.fresh(p,ttl): return p.read_bytes()
        return None

    def write_atomic(self,namespace,key,ext,data:bytes):
        p=self.path(namespace,key,ext); tmp=p.with_suffix(p.suffix+'.tmp')
        tmp.write_bytes(data); os.replace(tmp,p)

    def read_json(self,namespace,key,ttl):
        raw=self.read(namespace,key,'json',ttl)
        return json.loads(raw) if raw else None

    def read_json_stale(self,namespace,key):
        p=self.path(namespace,key,'json')
        if not p.exists():
            return None
        try:
            return json.loads(p.read_bytes())
        except (OSError, ValueError, TypeError):
            return None
    def write_json(self,namespace,key,obj):
        self.write_atomic(namespace,key,'json',json.dumps(obj,ensure_ascii=False).encode())
