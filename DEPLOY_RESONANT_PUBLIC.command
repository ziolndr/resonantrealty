#!/bin/zsh
set -euo pipefail
PORT="${RESONANT_PORT:-8797}"
DOMAIN="gui/$(id -u)"
launchctl kickstart -k "$DOMAIN/com.actualgeneralintelligence.resonant.server" >/dev/null 2>&1 || true
for _ in {1..60}; do curl -fsS --max-time 2 "http://127.0.0.1:$PORT/field/v1/manifest" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS --max-time 5 "http://127.0.0.1:$PORT/field/v1/manifest" >/dev/null || { echo "RESONANT server is not ready." >&2; exit 1; }
if command -v ngrok >/dev/null 2>&1; then
  pkill -f "ngrok http $PORT" >/dev/null 2>&1 || true
  nohup ngrok http "$PORT" --log=stdout --log-format=json > "$HOME/Library/Logs/SUMMON/resonant/public-tunnel.log" 2>&1 &
  for _ in {1..60}; do
    URL="$(curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((x.get("public_url","") for x in d.get("tunnels",[]) if x.get("proto")=="https"),""))' 2>/dev/null || true)"
    [[ -n "$URL" ]] && { echo "$URL"; open "$URL"; exit 0; }
    sleep 1
  done
fi
if command -v cloudflared >/dev/null 2>&1; then
  LOG="$HOME/Library/Logs/SUMMON/resonant/public-tunnel.log"
  pkill -f "cloudflared tunnel --url http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
  nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" > "$LOG" 2>&1 &
  for _ in {1..90}; do
    URL="$(grep -Eo 'https://[-a-z0-9]+\.trycloudflare\.com' "$LOG" | tail -1 || true)"
    [[ -n "$URL" ]] && { echo "$URL"; open "$URL"; exit 0; }
    sleep 1
  done
fi
echo "Install ngrok or cloudflared, then rerun this command." >&2
exit 1
