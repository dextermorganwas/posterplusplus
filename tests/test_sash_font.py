from pathlib import Path


def test_sash_uses_liberation_sans_bold():
    text = Path("app/core/sash.py").read_text()
    assert "LiberationSans-Bold.ttf" in text
    assert "NimbusSansNarrow" not in text


def test_sash_font_scale_is_fixed_by_config():
    text = Path(".env.example").read_text()
    assert "SASH_FONT_RATIO=0.056" in text
    assert "SASH_MIN_FONT_RATIO=0.056" in text
    assert "SASH_TAB_WIDTH_RATIO=0.46" in text
