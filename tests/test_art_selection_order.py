from app.providers import tmdb
from app.resolver import Resolver

def test_tmdb_pick_uses_first_item_in_language_without_scoring():
    items=[
        {"iso_639_1":"en","file_path":"first.jpg","vote_average":1,"vote_count":1},
        {"iso_639_1":"en","file_path":"second.jpg","vote_average":10,"vote_count":9999},
    ]
    got=tmdb.pick(items,["en"])
    assert got["file_path"]=="first.jpg"

def test_tmdb_pick_textless_backdrop_uses_first_neutral_item():
    items=[
        {"iso_639_1":None,"file_path":"first.jpg","vote_average":1},
        {"iso_639_1":None,"file_path":"second.jpg","vote_average":10},
    ]
    got=tmdb.pick(items,["en"],textless=True)
    assert got["file_path"]=="first.jpg"

def test_selection_cache_key_contains_algorithm_version():
    import inspect
    src=inspect.getsource(Resolver._select_art_uncached)
    assert 'v{settings.art_selection_algorithm_version}' in src


def test_tvdb_selection_does_not_score_artwork():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "resolver.py").read_text()
    block = src.split("async def _tvdb_selection", 1)[1].split("async def _tmdb_selection", 1)[0]
    assert "max(cat" not in block
    assert "max(xs" not in block
    assert "vote_average" not in block
    assert "score(a" not in block

def test_sash_defaults_are_larger_than_previous_version():
    from app.config import settings
    assert settings.sash_tab_height_ratio >= 0.085
    assert settings.sash_font_ratio == 0.048
    assert settings.sash_min_tab_width_ratio >= 0.32
