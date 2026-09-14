import os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def test_compose_uses_configurable_port_and_cache_path():
    data = yaml.safe_load((ROOT / "compose.yaml").read_text())
    svc = data["services"]["mediaart-router"]
    assert svc["ports"] == ["${PORT:-8000}:${PORT:-8000}"]
    assert svc["volumes"] == ["${CACHE_HOST_PATH:-./cache}:/app/cache"]


def test_entrypoint_drops_to_appuser():
    text = (ROOT / "entrypoint.sh").read_text()
    assert "chown -R appuser:appuser" in text
    assert "su -s /bin/sh appuser" in text


def test_encoded_artwork_spec_is_decoded_before_parsing():
    import sys
    sys.path.insert(0, str(ROOT))
    from app.main import parse_path

    encoded = "tmdb%3Amovie%3A1440098%26imdb%3Att36073210%26tvdb%3A.jpg"
    assert parse_path(encoded) == ("movie", "1440098", "tt36073210", None, "jpg")


def test_unencoded_artwork_spec_still_parses():
    import sys
    sys.path.insert(0, str(ROOT))
    from app.main import parse_path

    plain = "tmdb:movie:1514026&imdb:tt37281055&tvdb:372657.jpg"
    assert parse_path(plain) == ("movie", "1514026", "tt37281055", "372657", "jpg")
