#!/bin/zsh
set +e
APP="${RESONANT_APP:-$HOME/Library/Application Support/SUMMON/resonant}"
[[ -f "$APP/config.env" ]] && source "$APP/config.env"
PORT="${RESONANT_PORT:-8797}"
MIN="${RESONANT_MIN_PROPERTIES:-500}"
LABEL="com.actualgeneralintelligence.resonant.server"
echo "RESONANT"
echo "────────────────────────────────────────────────────────"
launchctl list | grep "$LABEL" || echo "server not loaded"
echo
MANIFEST="$(curl -fsS --max-time 5 "http://127.0.0.1:$PORT/field/v1/manifest" 2>/dev/null || true)"
if [[ -n "$MANIFEST" ]]; then
  printf '%s' "$MANIFEST" | python3 -m json.tool
  COUNT="$(printf '%s' "$MANIFEST" | python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("count") or 0))')"
  echo
  if (( COUNT < MIN )); then
    echo "ERROR: incomplete field ($COUNT properties; minimum $MIN)"
  else
    echo "field ready: $COUNT properties"
  fi
else
  echo "server not reachable on $PORT"
fi
