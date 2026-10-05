#!/usr/bin/env bash
# A/A jobs on this machine with the protocol of noise.yml, for the laptop vs runner comparison.
#
#   scripts/local-aa.sh [rounds] [runs]      # default: 6 rounds, 20 loads per variant
#
# One round = demo-spa and demo-heavy × devtools/simulate × abab/sequential = 8 jobs,
# about 15 minutes. Run it on an idle machine on mains power, with other apps closed:
# the point is to measure the laptop, not what else it is doing. Records go to
# results/local/<date>/ with the same schema as the CI data, so every report picks them up
# as a separate runner (`local:<platform>:<cpu>`).
set -euo pipefail

rounds="${1:-6}"
runs="${2:-20}"
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

dest="results/local/$(date -u +%F)"
mkdir -p "$dest"

pnpm --filter demo-spa build
pnpm --filter demo-spa preview > /tmp/perfgate-local-preview.log 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:4173/ > /dev/null && break
  sleep 1
done

# tree hash of the app package, as in CI: local and CI jobs of the same build share an epoch
app_build=$(git ls-tree HEAD -- apps/demo-spa | awk '{print substr($3,1,12)}')
if ! git diff --quiet HEAD -- apps/demo-spa; then
  echo "apps/demo-spa has uncommitted changes: the build does not match $app_build" >&2
  exit 1
fi

# keep the machine awake for the whole session
command -v caffeinate > /dev/null && caffeinate -i -w $$ &

for round in $(seq 1 "$rounds"); do
  for page in "demo-spa|" "demo-heavy|heavy.html"; do
    app="${page%%|*}"
    path="${page#*|}"
    for throttling in devtools simulate; do
      for mode in abab sequential; do
        id="local-$(date -u +%Y%m%dT%H%M%S)-aa-$app-$mode-$throttling"
        echo "round $round/$rounds: $id"
        base="http://127.0.0.1:4173/$path"
        pnpm perfgate collect \
          --url "$base" \
          --pr-url "$base" \
          --runs "$runs" \
          --mode "$mode" \
          --throttling "$throttling" \
          --app "$app" \
          --label aa \
          --app-build "$app_build" \
          --experiment "$id" \
          --out "$dest/$id.jsonl"
      done
    done
  done
done
echo "wrote $dest"
