#!/bin/bash
# Purpose: Submit final station-metric evaluation for exported Paloma model artifacts.

#SBATCH --job-name=paloma-final-metrics
#SBATCH --partition=amem
#SBATCH --qos=mem-normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=900G
#SBATCH --time=06:00:00
#SBATCH --output=remote_jobs/logs/paloma-final-metrics.%j.out
#SBATCH --error=remote_jobs/logs/paloma-final-metrics.%j.err

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
MODEL_RUN_ID="paloma_v1_${VARIABLE}"
TABLE="${DURABLE_PROJECT_DIR}/weather_reconstruction_model/outputs/general_training_tables/paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise_${VARIABLE}.csv"

cd "$PROJECT_DIR"
mkdir -p remote_jobs/logs

python weather_reconstruction_model/scripts/evaluate_final_model_station_metrics.py \
  --variable "$VARIABLE" \
  --model-run-root "$DURABLE_PROJECT_DIR/model_runs/paloma_v1" \
  --general-table "$TABLE" \
  --progress-rows 50000
