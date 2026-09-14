#!/bin/sh
set -eu

CACHE_PATH="${CACHE_DIR:-/app/cache}"

# Docker commonly creates a new bind-mounted cache directory as root. The app
# itself runs as UID 10001, so make the mount writable before dropping
# privileges. Once the top-level directory already belongs to appuser this is
# a cheap check and does not recursively walk the cache on every restart.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$CACHE_PATH"
    if [ "$(stat -c '%u' "$CACHE_PATH" 2>/dev/null || echo 0)" != "10001" ]; then
        chown -R appuser:appuser "$CACHE_PATH"
    fi
    exec su -s /bin/sh appuser -c 'exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers 1'
fi

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers 1
