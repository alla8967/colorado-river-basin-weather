#!/bin/bash
#SBATCH --job-name=paloma-export-hm
#SBATCH --partition=amem
#SBATCH --qos=mem-normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=900G
#SBATCH --time=08:00:00
#SBATCH --array=1-3
#SBATCH --output=ml_reconstruction/remote_jobs/logs/paloma-export-hm.%A_%a.out
#SBATCH --error=ml_reconstruction/remote_jobs/logs/paloma-export-hm.%A_%a.err

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

mkdir -p ml_reconstruction/remote_jobs/logs

if [[ -z "${VARIABLE:-}" ]]; then
  VARIABLES=(tavg tmin tmax)
  VARIABLE="${VARIABLES[$((${SLURM_ARRAY_TASK_ID:-1} - 1))]}"
fi

MODEL_RUN_ID="paloma_v1_${VARIABLE}"
TABLE="ml_reconstruction/weather_reconstruction_model/outputs/general_training_tables/paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise_${VARIABLE}.csv"

python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn \
  --check-cache-integrity

python ml_reconstruction/weather_reconstruction_model/scripts/export_final_model_artifact.py \
  --model-run-id "$MODEL_RUN_ID" \
  --general-table "$TABLE" \
  --variable "$VARIABLE" \
  --forest-trees 300 \
  --max-depth 20 \
  --min-samples-leaf 5 \
  --jobs "${SLURM_CPUS_PER_TASK:-48}" \
  --training-strategy full-forest \
  --exclude-pairwise-features

mkdir -p "$DURABLE_PROJECT_DIR/model_runs/paloma_v1"
rsync -av \
  "ml_reconstruction/weather_reconstruction_model/model_runs/${MODEL_RUN_ID}/" \
  "$DURABLE_PROJECT_DIR/model_runs/paloma_v1/${MODEL_RUN_ID}/"
