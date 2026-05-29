#!/bin/bash
#SBATCH --job-name=paloma-holdout
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=02:00:00
# Override this placeholder after chunk creation, for example:
# sbatch --array=1-27 ml_reconstruction/remote_jobs/run_paloma_holdout_array.sh
#SBATCH --array=1-1
#SBATCH --output=ml_reconstruction/remote_jobs/logs/paloma-holdout.%A_%a.out
#SBATCH --error=ml_reconstruction/remote_jobs/logs/paloma-holdout.%A_%a.err

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
CHUNK_ID=$(printf "%03d" "${SLURM_ARRAY_TASK_ID:-1}")
cd "$PROJECT_DIR"

mkdir -p ml_reconstruction/remote_jobs/logs

TABLE="ml_reconstruction/weather_reconstruction_model/outputs/general_training_tables/paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise_${VARIABLE}.csv"
CHUNK="ml_reconstruction/weather_reconstruction_model/outputs/paloma/station_holdout_chunks/${VARIABLE}/chunk_${CHUNK_ID}.csv"
OUTPUT_STEM="paloma_v1_${VARIABLE}_holdout_chunk_${CHUNK_ID}"

python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn \
  --check-cache-integrity

python ml_reconstruction/weather_reconstruction_model/scripts/train_station_holdout_model.py \
  "$TABLE" \
  --variable "$VARIABLE" \
  --station-list "$CHUNK" \
  --model-id "paloma_v1_${VARIABLE}" \
  --output-stem "$OUTPUT_STEM" \
  --predict-offset-from-baseline \
  --forest-trees 80 \
  --max-depth 14 \
  --min-samples-leaf 10 \
  --jobs "${SLURM_CPUS_PER_TASK:-32}" \
  --resume

mkdir -p "$DURABLE_PROJECT_DIR/ml_reconstruction/weather_reconstruction_model/outputs/reports"
mkdir -p "$DURABLE_PROJECT_DIR/ml_reconstruction/weather_reconstruction_model/outputs/predictions"
rsync -av \
  "ml_reconstruction/weather_reconstruction_model/outputs/reports/${OUTPUT_STEM}_station_metrics.csv" \
  "$DURABLE_PROJECT_DIR/ml_reconstruction/weather_reconstruction_model/outputs/reports/"
rsync -av \
  "ml_reconstruction/weather_reconstruction_model/outputs/predictions/${OUTPUT_STEM}_predictions.csv" \
  "$DURABLE_PROJECT_DIR/ml_reconstruction/weather_reconstruction_model/outputs/predictions/"
