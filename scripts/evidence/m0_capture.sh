#!/usr/bin/env bash
# M0 evidence capture: rebuild unmodified V1 in a fresh output folder inside the
# pinned report container, verify it, and compare analysis tables with the
# reference hashes in docs/evidence/m0/sandbox-run.json.
#
#   bash scripts/evidence/m0_capture.sh
#
# Writes only under reproduced/m0-container/ (git-ignored). Never edits tracked
# files, data/reference/ or results/. Exit status is 0 only when every step passed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
RUN_ROOT=reproduced/m0-container
OUT="$RUN_ROOT/artifacts"
EV="$RUN_ROOT/evidence"
IMAGE=health-report:m0
if [ -e "$RUN_ROOT" ]; then
  echo "Stop: $RUN_ROOT already exists. Move or delete it, then rerun." >&2
  exit 2
fi
mkdir -p "$EV"
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"

declare -a RESULTS=()
step() { # step <name> <command...>; logs to $EV/<name>.log
  local name="$1"; shift
  local t0=$SECONDS
  if "$@" >"$EV/$name.log" 2>&1; then RESULTS+=("PASS  $name ($((SECONDS-t0))s)")
  else RESULTS+=("FAIL  $name ($((SECONDS-t0))s) -> see $EV/$name.log"); fi
}
in_image() {
  docker run --rm -i --platform linux/amd64 --user "$LOCAL_UID:$LOCAL_GID" \
    --env HOME=/tmp --volume "$ROOT:/app" --workdir /app "$IMAGE" "$@"
}

{
  echo "recorded_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "commit=$(git rev-parse HEAD)"
  echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "worktree_dirty_files=$(git status --porcelain | wc -l)"
  echo "host=$(uname -srm)"
  echo "os=$( (lsb_release -ds 2>/dev/null) || grep PRETTY_NAME /etc/os-release | cut -d= -f2)"
  echo "docker=$(docker --version 2>&1)"
  echo "compose=$(docker compose version 2>&1)"
} > "$EV/environment.txt"

step docker_build docker build --platform linux/amd64 --file Dockerfile.report --tag "$IMAGE" .
docker image inspect "$IMAGE" --format 'image_id={{.Id}}' >> "$EV/environment.txt" 2>/dev/null
docker image inspect rocker/r-ver:4.3.2 --format 'base_digest={{index .RepoDigests 0}}' >> "$EV/environment.txt" 2>/dev/null
in_image sh -c 'echo "python=$(python --version 2>&1)"; echo "R=$(R --version | head -1)"; echo "quarto=$(quarto --version)"; echo "snakemake=$(snakemake --version)"' >> "$EV/environment.txt" 2>&1

step full_build       in_image snakemake --cores 2 --config out="$OUT"
step check_outputs    in_image python scripts/health_pipeline/check_outputs.py --out "$OUT"
step verify_release   in_image python scripts/health_pipeline/verify_release.py --out "$OUT"
step shiny_smoke      in_image Rscript tests/shiny_smoke.R "$OUT/reports/researcher/app"
step dashboard_smoke  in_image Rscript tests/dashboard_smoke.R "$OUT/reports/researcher/app"
noop() { in_image snakemake --dry-run --cores 1 --config out="$OUT" 2>&1 | tee /dev/stderr | grep -q 'Nothing to be done'; }
step noop_rebuild     noop
step compare_hashes   in_image python - "$OUT" <<'PY'
import hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[1]); ref = json.load(open('docs/evidence/m0/sandbox-run.json'))
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
bad = []
snap = json.load(open(out / 'snapshot.json'))['snapshot_id']
if snap != ref['snapshot_id']: bad.append(f'snapshot_id {snap}')
for n, v in ref['intermediate_sha256'].items():
    if h(out / n) != v: bad.append(n)
for s, files in ref['bundle_sha256'].items():
    for n, v in files.items():
        if h(out / 'reports' / s / 'data' / n) != v: bad.append(f'{s}/{n}')
print('snapshot_id', snap)
print('mismatches:', bad or 'none')
sys.exit(1 if bad else 0)
PY
( cd "$OUT" && find reports -maxdepth 2 -type f \( -name '*.html' -o -name '*.pdf' -o -name 'provenance*.json' \) -print0 \
    | sort -z | xargs -0 -r sha256sum ) > "$EV/artifact_sha256.txt" 2>/dev/null
cp "$OUT/release.json" "$EV/release.json" 2>/dev/null

SUMMARY="$EV/SUMMARY.txt"
{
  echo "===== ODESA M0 SUMMARY ====="
  cat "$EV/environment.txt"
  printf '%s\n' "${RESULTS[@]}"
  echo "artifacts_hashed=$(wc -l < "$EV/artifact_sha256.txt" 2>/dev/null || echo 0)"
  grep -h 'mismatches' "$EV/compare_hashes.log" 2>/dev/null
  for f in "$EV"/*.log; do
    if grep -qiE 'error|traceback|failed' "$f" && printf '%s\n' "${RESULTS[@]}" | grep -q "FAIL  $(basename "$f" .log) "; then
      echo "--- last lines of $(basename "$f") ---"; tail -n 12 "$f"
    fi
  done
  echo "===== END M0 SUMMARY ====="
} | tee "$SUMMARY"
! printf '%s\n' "${RESULTS[@]}" | grep -q '^FAIL'
