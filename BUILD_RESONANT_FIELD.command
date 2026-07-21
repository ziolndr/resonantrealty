#!/bin/zsh
set -euo pipefail

APP="${RESONANT_APP:-$HOME/Library/Application Support/SUMMON/resonant}"
CONFIG="$APP/config.env"
[[ -f "$CONFIG" ]] && source "$CONFIG"

PYTHON="${RESONANT_PYTHON:-$APP/venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  for candidate in \
    "$HOME/Downloads/venv/bin/python" \
    "$HOME/venv/bin/python" \
    "$(command -v python3 2>/dev/null || true)"
  do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" -c 'import numpy' >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi
[[ -n "$PYTHON" && -x "$PYTHON" ]] || { echo "Python 3 with numpy was not found." >&2; exit 1; }

PROVIDER="${REAL_ESTATE_PROVIDER:-homeharvest}"
MAX="${REAL_ESTATE_MAX_LISTINGS:-0}"
MIN="${RESONANT_MIN_PROPERTIES:-500}"
PAGE="${REAL_ESTATE_PAGE_SIZE:-500}"
EMBED="${ARBITER_EMBED_URL:-http://127.0.0.1:8000/v1/embed}"
BATCH="${ARBITER_EMBED_BATCH:-128}"
TIMEOUT="${ARBITER_EMBED_TIMEOUT:-900}"
PORT="${RESONANT_PORT:-8797}"
ROOT="$HOME/ARBITER_RESONANT_FIELD"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
SNAP="$ROOT/snapshots/$STAMP"
NEXT="$ROOT/field-next-$STAMP"
CURRENT="$ROOT/field-current"
ARCHIVE="$ROOT/archive"
STATE="$APP/state/listings.sqlite3"

mkdir -p "$SNAP" "$ARCHIVE" "$APP/state"

cat <<EOF
RESONANT PROPERTY FIELD
────────────────────────────────────────────────────────
provider: $PROVIDER
snapshot: $SNAP
embed:    $EMBED
EOF

ARGS=(
  --provider "$PROVIDER"
  --output "$SNAP/properties.jsonl"
  --state-db "$STATE"
  --max-listings "$MAX"
  --page-size "$PAGE"
)

case "$PROVIDER" in
  homeharvest)
    ARGS+=(--location "${HOMEHARVEST_LOCATIONS:-San Diego County}" --listing-types "${HOMEHARVEST_LISTING_TYPES:-for_sale,pending}")
    [[ "${HOMEHARVEST_SEQUENTIAL:-0}" == "1" ]] && ARGS+=(--sequential)
    [[ "${HOMEHARVEST_EXTRA_PROPERTY_DATA:-0}" == "1" ]] && ARGS+=(--extra-property-data)
    ;;
  simplyrets)
    [[ -n "${SIMPLYRETS_KEY:-}" && -n "${SIMPLYRETS_SECRET:-}" ]] || {
      echo "Set SIMPLYRETS_KEY and SIMPLYRETS_SECRET in $CONFIG" >&2; exit 1;
    }
    ARGS+=(--base-url "${SIMPLYRETS_BASE_URL:-https://api.simplyrets.com/properties}" --key "$SIMPLYRETS_KEY" --secret "$SIMPLYRETS_SECRET" --idx "${SIMPLYRETS_IDX:-null}")
    ;;
  reso)
    [[ -n "${RESO_BASE_URL:-}" && -n "${RESO_TOKEN:-}" ]] || {
      echo "Set RESO_BASE_URL and RESO_TOKEN in $CONFIG" >&2; exit 1;
    }
    ARGS+=(--base-url "$RESO_BASE_URL" --token "$RESO_TOKEN")
    [[ -n "${RESO_FILTER:-}" ]] && ARGS+=(--filter "$RESO_FILTER")
    [[ -n "${RESO_SELECT:-}" ]] && ARGS+=(--select "$RESO_SELECT")
    [[ -n "${RESO_EXPAND:-}" ]] && ARGS+=(--expand "$RESO_EXPAND")
    ;;
  *) echo "Unsupported REAL_ESTATE_PROVIDER=$PROVIDER" >&2; exit 1 ;;
esac

"$PYTHON" "$APP/bin/resonant_feed.py" "${ARGS[@]}"

FETCHED="$(wc -l < "$SNAP/properties.jsonl" | tr -d ' ')"
if (( FETCHED < MIN )); then
  echo "ERROR: HomeHarvest returned only $FETCHED properties; refusing to replace the live field with an incomplete snapshot." >&2
  echo "The current field was not changed." >&2
  exit 1
fi

echo "validated snapshot: $FETCHED properties"
rm -rf "$NEXT"
"$PYTHON" "$APP/bin/ARBITER_field_forge.py" init \
  --field-dir "$NEXT" \
  --name "RESONANT Property Field" \
  --dim 72 \
  --use-freq

"$PYTHON" "$APP/bin/ARBITER_field_forge.py" ingest-jsonl \
  --field-dir "$NEXT" \
  --path "$SNAP/properties.jsonl" \
  --source realestate \
  --id-field id \
  --title-field title \
  --text-field text \
  --type-field type \
  --year-field year \
  --url-field url \
  --pending-shard-size 5000 \
  --max-text-chars 12000 \
  --keep-original

"$PYTHON" "$APP/bin/ARBITER_field_forge.py" embed-pending \
  --field-dir "$NEXT" \
  --source realestate \
  --endpoint "$EMBED" \
  --batch-size "$BATCH" \
  --timeout "$TIMEOUT" \
  --delete-pending

"$PYTHON" "$APP/bin/ARBITER_field_forge.py" verify --field-dir "$NEXT"

if [[ -d "$CURRENT" ]]; then
  mv "$CURRENT" "$ARCHIVE/field-$STAMP"
fi
mv "$NEXT" "$CURRENT"
rm -rf "$ROOT/live-index"

DOMAIN="gui/$(id -u)"
LABEL="com.actualgeneralintelligence.resonant.server"
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null
fi

COUNT="$($PYTHON - "$CURRENT/field.json" <<'PY'
import json,sys
print(int(json.load(open(sys.argv[1])).get('embedded_records') or 0))
PY
)"

echo
echo "RESONANT FIELD READY · $COUNT embedded properties"
echo "http://127.0.0.1:$PORT/"
open -a "Google Chrome" "http://127.0.0.1:$PORT/?build=$STAMP" >/dev/null 2>&1 || true
