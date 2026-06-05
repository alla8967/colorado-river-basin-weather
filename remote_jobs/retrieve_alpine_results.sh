#!/usr/bin/env bash
# Purpose: Archive Alpine run outputs on the remote system and sync the snapshot back locally.

set -euo pipefail

REMOTE_USER="${REMOTE_USER:-alla8967}"
REMOTE_HOST="${REMOTE_HOST:-login.rc.colorado.edu}"
SNAPSHOT_NAME="${SNAPSHOT_NAME:-alpine_results_snapshot_2026_05_25}"
LOCAL_ROOT="${LOCAL_ROOT:-$(pwd)}"
LOCAL_ARTIFACT_ROOT="$LOCAL_ROOT/weather_reconstruction_artifacts/$SNAPSHOT_NAME"
REMOTE_PROJECT="/projects/$REMOTE_USER/crb_weather_project"
REMOTE_SCRATCH="/scratch/alpine/$REMOTE_USER/crb_weather_runs/current"
REMOTE_SNAPSHOT="$REMOTE_PROJECT/$SNAPSHOT_NAME"

if [[ ! -d "$LOCAL_ROOT/weather_reconstruction_model" ]]; then
  echo "Run this from the repository root, or set LOCAL_ROOT." >&2
  exit 1
fi

echo "Archiving Alpine outputs into: $REMOTE_SNAPSHOT"
ssh "$REMOTE_USER@$REMOTE_HOST" "SNAPSHOT_NAME='$SNAPSHOT_NAME' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

REMOTE_USER="${USER}"
SNAPSHOT_NAME="${SNAPSHOT_NAME:-alpine_results_snapshot_2026_05_25}"
REMOTE_PROJECT="/projects/$REMOTE_USER/crb_weather_project"
REMOTE_SCRATCH="/scratch/alpine/$REMOTE_USER/crb_weather_runs/current"
REMOTE_SNAPSHOT="$REMOTE_PROJECT/$SNAPSHOT_NAME"

mkdir -p "$REMOTE_SNAPSHOT"

if [[ -d "$REMOTE_SCRATCH/remote_jobs/logs" ]]; then
  mkdir -p "$REMOTE_SNAPSHOT/logs"
  rsync -av "$REMOTE_SCRATCH/remote_jobs/logs/" "$REMOTE_SNAPSHOT/logs/"
else
  echo "Warning: no remote_jobs/logs directory at $REMOTE_SCRATCH" >&2
fi

if [[ -d "$REMOTE_SCRATCH/weather_reconstruction_model/outputs" ]]; then
  mkdir -p "$REMOTE_SNAPSHOT/outputs"
  rsync -av "$REMOTE_SCRATCH/weather_reconstruction_model/outputs/" "$REMOTE_SNAPSHOT/outputs/"
else
  echo "Warning: no outputs directory at $REMOTE_SCRATCH" >&2
fi

if [[ -d "$REMOTE_SCRATCH/weather_reconstruction_model/model_runs" ]]; then
  mkdir -p "$REMOTE_SNAPSHOT/model_runs"
  rsync -av "$REMOTE_SCRATCH/weather_reconstruction_model/model_runs/" "$REMOTE_SNAPSHOT/model_runs/"
fi

if [[ -d "$REMOTE_SCRATCH/weather_reconstruction_model/cache" ]]; then
  mkdir -p "$REMOTE_SNAPSHOT/cache"
  rsync -av \
    --include='*_pairwise_skill_*.csv' \
    --include='*/' \
    --exclude='*' \
    "$REMOTE_SCRATCH/weather_reconstruction_model/cache/" \
    "$REMOTE_SNAPSHOT/cache/"
fi

find "$REMOTE_SNAPSHOT" -type f -printf '%p\t%s\n' | sort > "$REMOTE_SNAPSHOT/FILE_INVENTORY.tsv"
find "$REMOTE_SNAPSHOT" -type f \( -name "*.csv" -o -name "*.out" -o -name "*.err" -o -name "*.json" -o -name "*.html" \) \
  -print0 | xargs -0 -r sha256sum > "$REMOTE_SNAPSHOT/SHA256SUMS.txt"

echo "Archived $(find "$REMOTE_SNAPSHOT" -type f | wc -l | tr -d ' ') files."
REMOTE_SCRIPT

mkdir -p "$LOCAL_ARTIFACT_ROOT"
echo "Pulling Alpine snapshot into: $LOCAL_ARTIFACT_ROOT"
rsync -av "$REMOTE_USER@$REMOTE_HOST:$REMOTE_SNAPSHOT/" "$LOCAL_ARTIFACT_ROOT/"

echo "Building run summary."
python3 "$LOCAL_ROOT/weather_reconstruction_model/scripts/build_alpine_run_summary.py" "$LOCAL_ARTIFACT_ROOT"

echo "Done:"
echo "  $LOCAL_ARTIFACT_ROOT"
echo "  $LOCAL_ARTIFACT_ROOT/RUN_SUMMARY.csv"
echo "  $LOCAL_ARTIFACT_ROOT/RUN_SUMMARY.md"
