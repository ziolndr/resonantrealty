#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SOURCE="$ROOT/index.html"

if [ -f "$ROOT/web/index.html" ]; then
  SOURCE="$ROOT/web/index.html"
fi

if [ ! -s "$SOURCE" ]; then
  echo "Missing frontend: $SOURCE" >&2
  exit 1
fi

if ! grep -q '/field/v1/search' "$SOURCE"; then
  echo "Frontend is missing /field/v1/search" >&2
  exit 1
fi

if grep -q 'const SEED' "$SOURCE"; then
  echo "Hard-coded seed inventory is forbidden" >&2
  exit 1
fi

rm -rf "$ROOT/public"
mkdir -p "$ROOT/public"
cp "$SOURCE" "$ROOT/public/index.html"

cat > "$ROOT/public/robots.txt" <<'EOF'
User-agent: *
Allow: /
EOF

echo "Built $SOURCE -> $ROOT/public/index.html"
