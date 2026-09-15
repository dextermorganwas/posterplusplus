from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_sash_cache_setting_present():
    from app.config import settings
    assert settings.sash_cache_ttl_seconds > 0

def test_mdblist_media_kind():
    from app.resolver import _mdblist_media_kind
    assert _mdblist_media_kind("series") == "show"
    assert _mdblist_media_kind("tv") == "show"
    assert _mdblist_media_kind("movie") == "movie"
