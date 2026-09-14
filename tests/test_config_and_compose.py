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
