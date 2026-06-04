#!/bin/bash
#SBATCH --job-name=paloma-group-hm
#SBATCH --partition=amem
#SBATCH --qos=mem-normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=900G
#SBATCH --time=24:00:00
#SBATCH --array=1-5
#SBATCH --output=remote_jobs/logs/paloma-group-hm.%A_%a.out
#SBATCH --error=remote_jobs/logs/paloma-group-hm.%A_%a.err

set -euo pipefail

module purge
module load slurm/alpine
source /projects/$USER/miniforge3/etc/profile.d/conda.sh
conda activate crb-weather

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

PROJECT_DIR="${PROJECT_DIR:-/scratch/alpine/$USER/crb_weather_runs/current}"
DURABLE_PROJECT_DIR="${DURABLE_PROJECT_DIR:-/projects/$USER/crb_weather_project}"
VARIABLE="${VARIABLE:-tavg}"
FOREST_TREES="${FOREST_TREES:-80}"
MAX_DEPTH="${MAX_DEPTH:-14}"
MIN_SAMPLES_LEAF="${MIN_SAMPLES_LEAF:-10}"
GROUP_ID=$(printf "group_%03d" "${SLURM_ARRAY_TASK_ID:-1}")
cd "$PROJECT_DIR"

mkdir -p remote_jobs/logs

TABLE="weather_reconstruction_model/outputs/general_training_tables/paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise_${VARIABLE}.csv"
GROUP_FILE="weather_reconstruction_model/outputs/paloma/station_holdout_groups/${VARIABLE}/${GROUP_ID}.csv"
OUTPUT_STEM="paloma_v1_${VARIABLE}_group_holdout_${GROUP_ID}"

python weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn \
  --check-cache-integrity

python weather_reconstruction_model/scripts/train_station_holdout_model.py \
  "$TABLE" \
  --variable "$VARIABLE" \
  --station-group-list "$GROUP_FILE" \
  --model-id "paloma_v1_${VARIABLE}" \
  --output-stem "$OUTPUT_STEM" \
  --predict-offset-from-baseline \
  --forest-trees "$FOREST_TREES" \
  --max-depth "$MAX_DEPTH" \
  --min-samples-leaf "$MIN_SAMPLES_LEAF" \
  --jobs "${SLURM_CPUS_PER_TASK:-48}" \
  --resume

mkdir -p "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/reports"
mkdir -p "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/predictions"
mkdir -p "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/paloma/station_holdout_groups/${VARIABLE}"
rsync -av \
  "weather_reconstruction_model/outputs/reports/${OUTPUT_STEM}_station_metrics.csv" \
  "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/reports/"
rsync -av \
  "weather_reconstruction_model/outputs/predictions/${OUTPUT_STEM}_predictions.csv" \
  "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/predictions/"
rsync -av \
  "weather_reconstruction_model/outputs/paloma/station_holdout_groups/${VARIABLE}/" \
  "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/paloma/station_holdout_groups/${VARIABLE}/"
