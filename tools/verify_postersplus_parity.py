"""Verify the extracted PostersPlus sash/discovery implementation against a source checkout.

Usage:
  python tools/verify_postersplus_parity.py --postersplus /path/to/PostersPlus-dev
"""
from pathlib import Path
import argparse, difflib, hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]


def normalized_pp(pp_root: Path, name: str) -> str:
    s = (pp_root / name).read_text()
    if name == "discovery.py":
        s = s.replace(
            "from config import SASH_PRIORITY as DEFAULT_SASH_PRIORITY  # single source of truth",
            "from app.config import settings as _settings\nDEFAULT_SASH_PRIORITY = list(_settings.sash_priority)  # single source of truth",
        )
        s = s.replace("import config as _cfg", "from app import config as _cfg")
        s = s.replace(
            "from festivals import festival_label as resolve_festival_label, match_festival_keyword",
            "from app.core.festivals import festival_label as resolve_festival_label, match_festival_keyword",
        )
    elif name == "awards.py":
        s = s.replace("from config import (", "from app.config import (")
    elif name == "festivals.py":
        # No source imports need adapting in the extracted festivals module.
        pass
    return s


def configured_sashes(pp_root: Path) -> list[tuple[str, str]]:
    html = (pp_root / "configurator.html").read_text(errors="ignore")
    m = re.search(r"const SASH_SLOTS = \[(.*?)\];", html, re.S)
    if not m:
        raise RuntimeError("SASH_SLOTS not found")
    return re.findall(r"\{ id:'([^']+)',\s+label:'([^']*)'", m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--postersplus", type=Path, required=True)
    args = ap.parse_args()
    pp = args.postersplus
    if not (pp / "configurator.html").exists():
        raise SystemExit(f"Not a PostersPlus-dev checkout: {pp}")

    out = {"source_module_parity": {}, "sash_inventory_parity": {}}
    for pp_name, rel in {
        "discovery.py": "app/core/discovery.py",
        "awards.py": "app/core/awards.py",
        "festivals.py": "app/core/festivals.py",
    }.items():
        normalized = normalized_pp(pp, pp_name)
        mar = (ROOT / rel).read_text()
        out["source_module_parity"][pp_name] = {
            "exact_after_import_adaptation": normalized == mar,
            "diff_lines": len(list(difflib.unified_diff(normalized.splitlines(), mar.splitlines(), n=0))),
            "postersplus_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
            "mediaart_router_sha256": hashlib.sha256(mar.encode()).hexdigest(),
        }

    pp_slots = configured_sashes(pp)
    from app.core.sash_inventory import POSTERSPLUS_SASH_SLOTS
    mar_slots = list(POSTERSPLUS_SASH_SLOTS)
    out["sash_inventory_parity"] = {
        "postersplus_count": len(pp_slots),
        "mediaart_count": len(mar_slots),
        "exact_pairs": pp_slots == mar_slots,
        "missing_in_mediaart": [x for x in pp_slots if x not in mar_slots],
        "extra_in_mediaart": [x for x in mar_slots if x not in pp_slots],
    }
    print(json.dumps(out, indent=2))
    if any(not x.get("exact_after_import_adaptation", True) for x in out["source_module_parity"].values()):
        return 2
    if not out["sash_inventory_parity"]["exact_pairs"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
