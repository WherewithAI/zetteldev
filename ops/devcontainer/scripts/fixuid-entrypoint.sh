#!/bin/sh
set -eu

# Ensure cache mount points exist so fixuid can adjust ownership.
paths="
/caches
/caches/pixi
/caches/pixi/uv-cache
/caches/uv
/caches/pip
/caches/jupyter_cache
/caches/huggingface
/var/log/zdev/egress
"

for path in $paths; do
    mkdir -p "$path"
done

# Ensure existing cache volumes are writable before fixuid remaps IDs.
chown -R dev:dev /caches 2>/dev/null || true
chown -R dev:dev /var/log/zdev/egress 2>/dev/null || true

/usr/local/bin/fixuid -q

# fixuid sets UID/GID; enforce ownership again for mounts created after remap.
chown -R dev:dev /caches 2>/dev/null || true
chown -R dev:dev /var/log/zdev/egress 2>/dev/null || true

exec "$@"
