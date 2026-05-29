#!/bin/bash
#SBATCH --job-name=crb-medium
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --time=08:00:00
#SBATCH --output=ml_reconstruction/remote_jobs/logs/crb-medium.%j.out
#SBATCH --error=ml_reconstruction/remote_jobs/logs/crb-medium.%j.err

set -euo pipefail

module purge
module load slurm/alpine
module load anaconda

# If you create a named conda environment on Alpine, uncomment and edit this:
# conda activate crb-weather

PROJECT_DIR="${PROJECT_DIR:-/scratch/alpine/$USER/crb_weather_runs/current}"
cd "$PROJECT_DIR"

mkdir -p ml_reconstruction/remote_jobs/logs

python ml_reconstruction/weather_reconstruction_model/scripts/check_remote_environment.py \
  --require-sklearn

python ml_reconstruction/weather_reconstruction_model/scripts/run_remote_pipeline.py \
  --preset medium
