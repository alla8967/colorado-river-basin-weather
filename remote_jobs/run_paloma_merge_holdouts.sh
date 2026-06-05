#!/bin/bash
# Purpose: Submit the merge step that consolidates Paloma holdout chunk outputs.

#SBATCH --job-name=paloma-merge
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=remote_jobs/logs/paloma-merge.%j.out
#SBATCH --error=remote_jobs/logs/paloma-merge.%j.err

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
cd "$PROJECT_DIR"

mkdir -p remote_jobs/logs

OUTPUT="weather_reconstruction_model/outputs/paloma/paloma_v1_${VARIABLE}_station_holdout_master.csv"

python weather_reconstruction_model/scripts/merge_station_holdout_results.py \
  --input-dir weather_reconstruction_model/outputs/reports \
  --pattern "paloma_v1_${VARIABLE}_holdout_chunk_*_station_metrics.csv" \
  --output "$OUTPUT" \
  --model-id "paloma_v1_${VARIABLE}" \
  --variable "$VARIABLE"

mkdir -p "$DURABLE_PROJECT_DIR/model_runs/paloma_v1/validation"
mkdir -p "$DURABLE_PROJECT_DIR/model_runs/paloma_v1/logs"
rsync -av weather_reconstruction_model/outputs/paloma/ \
  "$DURABLE_PROJECT_DIR/model_runs/paloma_v1/validation/"
rsync -av remote_jobs/logs/ \
  "$DURABLE_PROJECT_DIR/model_runs/paloma_v1/logs/"
