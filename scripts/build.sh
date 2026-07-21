#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SOURCE="$ROOT/web/index.html"
[ -s "$SOURCE" ] || SOURCE="$ROOT/index.html"
[ -s "$SOURCE" ] || { echo "Missing RESONANT frontend" >&2; exit 1; }
grep -q '20260721-image-delivery-v3' "$SOURCE"
grep -q '/field/v1/search' "$SOURCE"
! grep -q 'const SEED' "$SOURCE"
rm -rf "$ROOT/public"
mkdir -p "$ROOT/public"
cp "$SOURCE" "$ROOT/public/index.html"
printf 'User-agent: *\nAllow: /\n' > "$ROOT/public/robots.txt"
echo "Built RESONANT frontend"
