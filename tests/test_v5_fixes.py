from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image


def test_tvdb_series_artwork_excludes_season_and_episode_art():
    from app.providers.tvdb import is_series_level_artwork
    assert is_series_level_artwork({"type": 1, "seasonId": None, "episodeId": None})
    assert is_series_level_artwork({"type": 1, "seasonId": 0, "episodeId": 0})
    assert not is_series_level_artwork({"type": 1, "seasonId": 12345})
    assert not is_series_level_artwork({"type": 1, "episodeId": 98765})


def test_sash_output_has_fixed_postersplus_canvas():
    from app.core.sash import draw_status_sash
    from app.config import settings
    out = draw_status_sash(Image.new("RGB", (500, 750), (20, 20, 20)), "Airing", (80, 80, 80), (255, 255, 255), settings)
    assert out.size == (500, 750)


def test_algorithm_version_bumped():
    from app.config import settings
    assert settings.art_selection_algorithm_version >= 4
    assert settings.sash_bottom_inset_ratio >= 0.012
