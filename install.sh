#!/usr/bin/env bash
# Install Arlecchino pet skins into the Codex / ChatGPT desktop app.
# Usage:
#   bash install.sh                    # install every pet in pets/
#   bash install.sh arlecchino-chibi   # install one

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src_dir="$root/pets"
dest_dir="$HOME/.codex/pets"

[ -d "$src_dir" ] || { echo "pets/ not found next to this script" >&2; exit 1; }
mkdir -p "$dest_dir"

if [ "$#" -gt 0 ]; then
  targets=()
  for name in "$@"; do
    [ -d "$src_dir/$name" ] || { echo "unknown pet '$name'; available: $(ls "$src_dir" | tr '\n' ' ')" >&2; exit 1; }
    targets+=("$src_dir/$name")
  done
else
  targets=("$src_dir"/*/)
fi

for dir in "${targets[@]}"; do
  name="$(basename "$dir")"
  if [ ! -f "$dir/pet.json" ] || [ ! -f "$dir/spritesheet.webp" ]; then
    echo "skip $name (missing pet.json or spritesheet.webp)" >&2
    continue
  fi
  rm -rf "$dest_dir/$name"
  cp -R "$dir" "$dest_dir/$name"
  echo "installed $name -> $dest_dir/$name"
done

echo
echo "Done. Fully quit the app and relaunch, then pick the pet under"
echo "Settings -> Personalization -> Pets."
