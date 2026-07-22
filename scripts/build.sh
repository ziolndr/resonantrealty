#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SOURCE="$ROOT/web/index.html"

if [ ! -s "$SOURCE" ]; then
  SOURCE="$ROOT/index.html"
fi

test -s "$SOURCE"
grep -q '/field/v1/search' "$SOURCE"
! grep -q 'const SEED' "$SOURCE"

rm -rf "$ROOT/public"
mkdir -p "$ROOT/public"

cp "$SOURCE" "$ROOT/public/index.html"
cp "$ROOT/assets/favicon.ico" "$ROOT/public/favicon.ico"

cat > "$ROOT/public/robots.txt" <<'EOF'
User-agent: *
Allow: /
EOF

echo "Built RESONANT static frontend"
