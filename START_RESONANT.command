#!/bin/zsh
set -euo pipefail
APP="${RESONANT_APP:-$HOME/Library/Application Support/SUMMON/resonant}"
[[ -f "$APP/config.env" ]] && source "$APP/config.env"
PORT="${RESONANT_PORT:-8797}"
MIN="${RESONANT_MIN_PROPERTIES:-500}"
DOMAIN="gui/$(id -u)"
LABEL="com.actualgeneralintelligence.resonant.server"
FIELD="$HOME/ARBITER_RESONANT_FIELD/field-current/field.json"
COUNT=0
if [[ -f "$FIELD" ]]; then
  COUNT="$($APP/venv/bin/python - "$FIELD" <<'PYCOUNT'
import json,sys
try: print(int(json.load(open(sys.argv[1])).get("embedded_records") or 0))
except Exception: print(0)
PYCOUNT
)"
fi
if (( COUNT < MIN )); then
  /bin/zsh "$APP/BUILD_RESONANT_FIELD.command"
fi
launchctl kickstart -k "$DOMAIN/$LABEL"
for _ in {1..90}; do
  curl -fsS --max-time 2 "http://127.0.0.1:$PORT/field/v1/manifest" >/dev/null 2>&1 && break
  sleep 1
done
open -a "Google Chrome" "http://127.0.0.1:$PORT/" >/dev/null 2>&1 || true
