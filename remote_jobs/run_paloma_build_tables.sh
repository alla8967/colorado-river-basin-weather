#!/bin/bash
#SBATCH --job-name=paloma-tables
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
#SBATCH --array=1-3
#SBATCH --output=remote_jobs/logs/paloma-tables.%A_%a.out
#SBATCH --error=remote_jobs/logs/paloma-tables.%A_%a.err

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
cd "$PROJECT_DIR"

mkdir -p remote_jobs/logs

if [[ -z "${VARIABLE:-}" ]]; then
  VARIABLES=(tavg tmin tmax)
  VARIABLE="${VARIABLES[$((${SLURM_ARRAY_TASK_ID:-1} - 1))]}"
fi

TABLE_STEM="paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise_${VARIABLE}"

python weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn \
  --check-cache-integrity

python weather_reconstruction_model/scripts/run_remote_pipeline.py \
  --preset paloma-full \
  --skip-pairwise \
  --variable "$VARIABLE" \
  --only-build

mkdir -p "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/general_training_tables"
rsync -av \
  "weather_reconstruction_model/outputs/general_training_tables/${TABLE_STEM}.csv" \
  "$DURABLE_PROJECT_DIR/weather_reconstruction_model/outputs/general_training_tables/"
