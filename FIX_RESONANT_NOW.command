#!/bin/zsh
set -euo pipefail
SOURCE="${0:A:h}"
APP="$HOME/Library/Application Support/SUMMON/resonant"

mkdir -p "$APP"
rsync -a --delete --exclude config.env --exclude venv --exclude .git "$SOURCE/" "$APP/"
[[ -f "$APP/config.env" ]] || cp "$APP/config/config.env.example" "$APP/config.env"

if grep -q '^REAL_ESTATE_PROVIDER=' "$APP/config.env"; then
  sed -i '' -E 's/^REAL_ESTATE_PROVIDER=.*/REAL_ESTATE_PROVIDER=homeharvest/' "$APP/config.env"
else
  echo 'REAL_ESTATE_PROVIDER=homeharvest' >> "$APP/config.env"
fi

if grep -q '^RESONANT_MIN_PROPERTIES=' "$APP/config.env"; then
  sed -i '' -E 's/^RESONANT_MIN_PROPERTIES=.*/RESONANT_MIN_PROPERTIES=50/' "$APP/config.env"
else
  echo 'RESONANT_MIN_PROPERTIES=50' >> "$APP/config.env"
fi

exec /bin/zsh "$APP/INSTALL_RESONANT.command"
