#!/bin/bash
# Purpose: Submit a short smoke-test reconstruction job to validate the Alpine environment.

#SBATCH --job-name=crb-smoke
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=01:00:00
#SBATCH --output=remote_jobs/logs/crb-smoke.%j.out
#SBATCH --error=remote_jobs/logs/crb-smoke.%j.err

set -euo pipefail

module purge
module load slurm/alpine
module load anaconda

# If you create a named conda environment on Alpine, uncomment and edit this:
# conda activate crb-weather

PROJECT_DIR="${PROJECT_DIR:-/scratch/alpine/$USER/crb_weather_runs/current}"
cd "$PROJECT_DIR"

mkdir -p remote_jobs/logs

python weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn \
  --check-cache-integrity

python weather_reconstruction_model/scripts/run_remote_pipeline.py \
  --preset smoke
