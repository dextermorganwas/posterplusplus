from unittest.mock import patch
from datetime import date, timedelta


TODAY = date(2026, 9, 14)


def test_movies_do_not_inherit_tv_awards():
    from app.core.awards import parse_mdblist_awards, tmdb_id_awards
    # 105 is intentionally both Back to the Future (movie) and Sex and the City (TV).
    wins, noms = parse_mdblist_awards([], tmdb_id=105, media_type="movie")
    assert "Emmy Winner" not in wins
    assert "Emmy Nominee" not in noms
    tv_wins, _ = parse_mdblist_awards([], tmdb_id=105, media_type="tv")
    assert "Emmy Winner" in tv_wins


def test_released_movie_with_only_future_theatrical_date_is_production():
    from app.core.release_status import _compute_movie_status
    future = TODAY + timedelta(days=7)
    with patch('app.core.release_status.date') as mocked_date:
        mocked_date.today.return_value = TODAY
        assert _compute_movie_status(future, None, None, "Released") == "Production"


def test_released_movie_with_future_premiere_is_production():
    from app.core.release_status import _compute_movie_status
    future = TODAY + timedelta(days=10)
    with patch('app.core.release_status.date') as mocked_date:
        mocked_date.today.return_value = TODAY
        assert _compute_movie_status(None, None, None, "Released", future) == "Production"


def test_limited_theatrical_counts_as_cinema():
    from app.core.release_status import _compute_movie_status
    with patch('app.core.release_status.date') as mocked_date:
        mocked_date.today.return_value = TODAY
        past = TODAY - timedelta(days=1)
        assert _compute_movie_status(past, None, None, "Released") == "Cinema"


def test_release_info_current_legacy_rows_are_refreshed_once():
    from app.core.release_status import _release_info_is_current
    assert not _release_info_is_current({"status":"Streaming","theatrical_date":None,"digital_date":None,"physical_date":None})
    assert _release_info_is_current({"status":"Production","premiere_date":None})


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
    async def get(self, *args, **kwargs):
        return _FakeResponse(self.payload)


def test_release_dates_treat_limited_theatrical_and_premiere_as_evidence():
    import asyncio
    from unittest.mock import patch
    from datetime import date, timedelta
    from app.core.release_status import fetch_movie_release_info

    today = date.today()
    premiere = today + timedelta(days=5)
    limited = today + timedelta(days=10)
    payload = {"results": [{"release_dates": [
        {"type": 1, "release_date": premiere.isoformat() + "T00:00:00Z"},
        {"type": 2, "release_date": limited.isoformat() + "T00:00:00Z"},
    ]}]}
    fake = _FakeClient(payload)
    with patch("app.core.release_status.get_cached_movie_release_info", return_value=None), \
         patch("app.core.release_status.set_cached_movie_release_info"):
        info = asyncio.run(fetch_movie_release_info(fake, "999999", "key", "Released"))
    assert info["premiere_date"] == premiere.isoformat()
    assert info["theatrical_date"] == limited.isoformat()
    assert info["status"] == "Production"


def test_algorithm_version_bumped_for_latest_postersplus_fixes():
    from app.config import settings
    assert settings.art_selection_algorithm_version >= 6


def test_mdblist_uses_show_not_tv_for_series():
    from app.resolver import _mdblist_media_kind
    assert _mdblist_media_kind("series") == "show"
    assert _mdblist_media_kind("tv") == "show"
    assert _mdblist_media_kind("movie") == "movie"


def test_mdblist_400_is_cached_as_empty_and_not_logged_as_keyword_failure(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace
    import app.resolver as resolver_module

    class Resp:
        status_code = 400
        def json(self):
            return {"error": "Invalid media_type. Must be 'movie' or 'show'."}

    r = resolver_module.Resolver()
    r.cache = r.cache.__class__(str(tmp_path))
    monkeypatch.setattr(
        resolver_module,
        "settings",
        SimpleNamespace(mdblist_api_key="test-key", discovery_cache_ttl_seconds=3600),
    )

    async def fake_get(*args, **kwargs):
        return Resp()

    monkeypatch.setattr(r, "_get", fake_get)
    monkeypatch.setattr(r, "client", object())
    result = asyncio.run(r._load_keywords("series", "123", "tt1234567"))
    assert result == []
    cached = r.cache.read_json("discovery", "imdb:show:tt1234567", 999999)
    assert cached == {"keywords": [], "missing": False, "invalid": True}
