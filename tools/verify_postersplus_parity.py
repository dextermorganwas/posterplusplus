from pathlib import Path
import difflib, hashlib, json, re
ROOT=Path(__file__).resolve().parents[1]
PP=Path('/mnt/data/pp_src/PostersPlus-dev')


def normalized_pp(name: str) -> str:
    s=(PP/name).read_text()
    if name=='discovery.py':
        s=s.replace('from config import SASH_PRIORITY as DEFAULT_SASH_PRIORITY  # single source of truth','from app.config import settings as _settings\nDEFAULT_SASH_PRIORITY = list(_settings.sash_priority)  # single source of truth')
        s=s.replace('import config as _cfg','from app import config as _cfg')
        s=s.replace('from festivals import festival_label as resolve_festival_label, match_festival_keyword','from app.core.festivals import festival_label as resolve_festival_label, match_festival_keyword')
    elif name=='awards.py':
        s=s.replace('from config import (','from app.config import (')
    return s


def configured_sashes() -> list[tuple[str,str]]:
    html=(PP/'configurator.html').read_text(errors='ignore')
    m=re.search(r'const SASH_SLOTS = \[(.*?)\];',html,re.S)
    if not m: raise RuntimeError('SASH_SLOTS not found')
    return re.findall(r"\{ id:'([^']+)',\s+label:'([^']*)'",m.group(1))

out={'source_module_parity':{},'sash_inventory_parity':{}}
for pp_name, rel in {'discovery.py':'app/core/discovery.py','awards.py':'app/core/awards.py','festivals.py':'app/core/festivals.py'}.items():
    pp=normalized_pp(pp_name); mar=(ROOT/rel).read_text()
    out['source_module_parity'][pp_name]={'exact_after_import_adaptation':pp==mar,'diff_lines':len(list(difflib.unified_diff(pp.splitlines(),mar.splitlines(),n=0))),'postersplus_sha256':hashlib.sha256(pp.encode()).hexdigest(),'mediaart_router_sha256':hashlib.sha256(mar.encode()).hexdigest()}

pp_slots=configured_sashes()
from app.core.sash_inventory import POSTERSPLUS_SASH_SLOTS
mar_slots=list(POSTERSPLUS_SASH_SLOTS)
out['sash_inventory_parity']={'postersplus_count':len(pp_slots),'mediaart_count':len(mar_slots),'exact_pairs':pp_slots==mar_slots,'missing_in_mediaart':[x for x in pp_slots if x not in mar_slots],'extra_in_mediaart':[x for x in mar_slots if x not in pp_slots]}
print(json.dumps(out,indent=2))
if any(not x.get('exact_after_import_adaptation',True) for x in out['source_module_parity'].values()): raise SystemExit(2)
if not out['sash_inventory_parity']['exact_pairs']: raise SystemExit(3)
