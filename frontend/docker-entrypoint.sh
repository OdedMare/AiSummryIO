#!/bin/sh
# Resolve BACKEND_URL at container start, then hand off to the server.
#
# next build compiles the /api/* rewrite target into .next, so without this the
# container would proxy to whatever host the image was built against. Each
# start regenerates the affected artifacts from the pristine .template copies
# made at build time, which keeps this idempotent: restarting with a different
# BACKEND_URL takes effect, restarting with the same one changes nothing.

set -eu

cd /app

SENTINEL_FILE=.backend-url-sentinel
FILE_LIST=.backend-url-files

if [ ! -s "$SENTINEL_FILE" ] || [ ! -s "$FILE_LIST" ]; then
    echo "docker-entrypoint: $SENTINEL_FILE or $FILE_LIST is missing — this image was not built from frontend/Dockerfile" >&2
    exit 1
fi

sentinel=$(cat "$SENTINEL_FILE")

# The default matches next.config.ts and suits `docker run` against a backend
# published on the host network; anything else must pass BACKEND_URL.
target="${BACKEND_URL:-http://127.0.0.1:8000}"

# A trailing slash would make every proxied request `//api/...`.
while :; do
    case "$target" in
        */) target="${target%/}" ;;
        *) break ;;
    esac
done

case "$target" in
    http://*|https://*) ;;
    *)
        echo "docker-entrypoint: BACKEND_URL must start with http:// or https:// (got '$target')" >&2
        exit 1
        ;;
esac

# `|` is the sed delimiter below, and no legitimate URL carries one.
case "$target" in
    *"|"*)
        echo "docker-entrypoint: BACKEND_URL must not contain '|' (got '$target')" >&2
        exit 1
        ;;
esac

while IFS= read -r artifact; do
    [ -n "$artifact" ] || continue
    if [ ! -f "$artifact.template" ]; then
        echo "docker-entrypoint: $artifact.template is missing" >&2
        exit 1
    fi
    sed "s|$sentinel|$target|g" "$artifact.template" > "$artifact"
done < "$FILE_LIST"

echo "docker-entrypoint: /api/* proxies to $target"

exec "$@"
