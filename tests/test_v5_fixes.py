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
    assert settings.art_selection_algorithm_version >= 5
    assert settings.sash_bottom_inset_ratio >= 0.012
    assert settings.sash_font_ratio == 0.054
    assert settings.sash_tab_width_ratio == 0.50


def test_sash_fills_to_bottom_edge_and_lowers_text():
    from app.core.sash import draw_status_sash
    from app.config import settings
    out = draw_status_sash(Image.new("RGB", (500, 750), (10, 10, 10)), "Airing", (90, 80, 70), (255, 255, 255), settings)
    # Bottom row must be sash-colored so no source-poster strip can peek below it.
    assert out.getpixel((250, 749)) == (90, 80, 70)


def test_sash_text_uses_fixed_baseline_for_labels_with_and_without_descenders():
    from app.core.sash import draw_status_sash
    from app.config import settings

    base = Image.new("RGB", (500, 750), (15, 15, 15))
    a = draw_status_sash(base, "#4 Today", (70, 70, 70), (255, 255, 255), settings)
    b = draw_status_sash(base, "New", (70, 70, 70), (255, 255, 255), settings)

    # The exact glyph ink boxes differ, but their baselines must be driven by the
    # same typographic coordinate rather than by each label's bbox height.
    # Regression guard: implementation must use a fixed baseline anchor.
    import inspect
    src = inspect.getsource(draw_status_sash)
    assert "anchor=\"ls\"" in src
    assert 'baseline_local = round' in src
    assert "_font_that_fits" not in src
    assert "_font_fixed" in src


def test_sash_uses_one_font_size_for_all_labels():
    from pathlib import Path
    from app.config import settings
    from app.core import sash
    assert settings.sash_font_ratio == 0.054
    assert settings.sash_min_font_ratio == 0.054
    assert "_font_that_fits" not in Path(sash.__file__).read_text()
    assert "_font_fixed" in Path(sash.__file__).read_text()
