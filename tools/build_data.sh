#!/bin/sh
# Builds the mod's data/ from tools/hellforge-data.json: the live resources from Steam's install on C: (named explicitly:
# HellForge's own Steam lookup can pick another, older Helldivers 2 install), against HellForge's game copy.
set -e
here=$(cd "$(dirname "$0")" && pwd)
spec=$(mktemp -d)
cp "$here/hellforge-data.json" "$spec/"
echo '{"format":1,"id":"goose.scope-of-authority-data","name":"data","version":"0","gameplay":false}' > "$spec/hellforge-mod.json"
rm -rf "$here/../mod/data"
"${HELLFORGE:-F:/Hellforge}/app/cli/HellForge.Cli.exe" build-data --mod "$spec" --game-data "${HELLFORGE:-F:/Hellforge}/game/data" \
    --steam-data "${STEAM_HD2:-C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2}/data" --out "$here/../mod/data" > /dev/null
rm -rf "$spec"
OVERRIDES="${OVERRIDES-avatar,audio}" py -I "$here/overrides.py" 2>/dev/null || python -I "$here/overrides.py"
ls "$here/../mod/data" | wc -l
