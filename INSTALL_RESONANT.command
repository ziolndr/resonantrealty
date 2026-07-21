#!/bin/zsh
set -euo pipefail
SOURCE="${0:A:h}"
APP="$HOME/Library/Application Support/SUMMON/resonant"
LAUNCH="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH/com.actualgeneralintelligence.resonant.server.plist"
DOMAIN="gui/$(id -u)"
LABEL="com.actualgeneralintelligence.resonant.server"

mkdir -p "$APP" "$LAUNCH" "$HOME/Library/Logs/SUMMON/resonant"
rsync -a --delete --exclude config.env --exclude venv "$SOURCE/" "$APP/"
[[ -f "$APP/config.env" ]] || cp "$APP/config/config.env.example" "$APP/config.env"
# Keep the default credential-free collector unless an optional provider is explicitly configured.
if ! grep -Eq '^REAL_ESTATE_PROVIDER=(homeharvest|simplyrets|reso)[[:space:]]*$' "$APP/config.env"; then
  sed -i '' -E 's/^REAL_ESTATE_PROVIDER=.*/REAL_ESTATE_PROVIDER=homeharvest/' "$APP/config.env"
fi
grep -q '^HOMEHARVEST_LOCATIONS=' "$APP/config.env" || cat >> "$APP/config.env" <<'CFG'
HOMEHARVEST_LOCATIONS="San Diego County, CA|San Diego, CA|Chula Vista, CA|Oceanside, CA|Escondido, CA|Carlsbad, CA|El Cajon, CA|Vista, CA|San Marcos, CA|Encinitas, CA"
HOMEHARVEST_LISTING_TYPES="for_sale,pending"
HOMEHARVEST_SEQUENTIAL=0
HOMEHARVEST_EXTRA_PROPERTY_DATA=0
RESONANT_MIN_PROPERTIES=50
CFG
chmod +x "$APP"/*.command "$APP/bin"/*.py

SYSTEM_PYTHON="$(command -v python3 2>/dev/null || true)"
[[ -n "$SYSTEM_PYTHON" && -x "$SYSTEM_PYTHON" ]] || { echo "Python 3 was not found." >&2; exit 1; }

VENV="$APP/venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$SYSTEM_PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade pip
"$VENV/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade -r "$APP/requirements.txt"
PYTHON="$VENV/bin/python"

source "$APP/config.env"
PORT="${RESONANT_PORT:-8797}"


# Keep the current field live until BUILD_RESONANT_FIELD.command has fully verified its replacement.
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array>
<string>$PYTHON</string>
<string>$APP/bin/RESONANT_live_field_server.py</string>
<string>serve</string>
<string>--field-dir</string><string>$HOME/ARBITER_RESONANT_FIELD/field-current</string>
<string>--live-dir</string><string>$HOME/ARBITER_RESONANT_FIELD/live-index</string>
<string>--include-source</string><string>realestate</string>
<string>--host</string><string>127.0.0.1</string>
<string>--port</string><string>$PORT</string>
<string>--embed-url</string><string>${ARBITER_EMBED_URL:-http://127.0.0.1:8000/v1/embed}</string>
<string>--html</string><string>$APP/web/index.html</string>
<string>--assets-dir</string><string>$APP/web</string>
</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>ThrottleInterval</key><integer>10</integer>
<key>StandardOutPath</key><string>$HOME/Library/Logs/SUMMON/resonant/server.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/SUMMON/resonant/server.error.log</string>
<key>EnvironmentVariables</key><dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
</dict></plist>
EOF
plutil -lint "$PLIST"

cp "$APP/BUILD_RESONANT_FIELD.command" "$HOME/Downloads/BUILD_RESONANT_FIELD.command"
cp "$APP/START_RESONANT.command" "$HOME/Downloads/START_RESONANT.command"
cp "$APP/RESONANT_STATUS.command" "$HOME/Downloads/RESONANT_STATUS.command"
cp "$APP/FIX_RESONANT_NOW.command" "$HOME/Downloads/FIX_RESONANT_NOW.command"
cp "$APP/DEPLOY_RESONANT_PUBLIC.command" "$HOME/Downloads/DEPLOY_RESONANT_PUBLIC.command"
chmod +x "$HOME/Downloads/BUILD_RESONANT_FIELD.command" "$HOME/Downloads/START_RESONANT.command" "$HOME/Downloads/RESONANT_STATUS.command" "$HOME/Downloads/FIX_RESONANT_NOW.command" "$HOME/Downloads/DEPLOY_RESONANT_PUBLIC.command"

launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
echo "Fetching and embedding the current San Diego County property field..."
/bin/zsh "$APP/BUILD_RESONANT_FIELD.command"
launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null || true
launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true

echo
echo "RESONANT installed"
echo "Site:   http://127.0.0.1:$PORT/"
echo "Config: $APP/config.env"
echo "Build:  $HOME/Downloads/BUILD_RESONANT_FIELD.command"
