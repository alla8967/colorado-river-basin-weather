# Remote Transfer Checklist

Use this checklist when copying the project to Alpine.

The goal is to transfer only the files needed for remote model training, while leaving bulky archives and local scratch output behind.

## Recommended Alpine Layout

Keep a durable copy in `/projects` and run jobs from `/scratch/alpine`.

```text
/projects/$USER/crb_weather_project
/scratch/alpine/$USER/crb_weather_runs/current
```

Suggested flow:

```bash
rsync -av /projects/$USER/crb_weather_project/ /scratch/alpine/$USER/crb_weather_runs/current/
cd /scratch/alpine/$USER/crb_weather_runs/current
```

## Upload These

Required source code and scripts:

```text
Makefile
README.md
docs/remote_runs/run_manifest.md
docs/remote_runs/transfer_checklist.md
C++_Weather_Station_Proxy_Engine/
Station_Engine_Server/
station-proxy-backend/
tests/
weather_reconstruction_model/
remote_jobs/
```

Required NOAA station metadata and prepared temperature files:

```text
NOAA_Inventory_Sort/target_station_candidates.csv
NOAA_Inventory_Sort/hub_station_candidates.csv
NOAA_Inventory_Sort/target_daily_app_ready.csv
NOAA_Inventory_Sort/hub_daily_app_ready.csv
```

Required processed terrain features:

```text
terrain_data/processed/station_terrain_features.csv
```

Strongly recommended cache:

```text
weather_reconstruction_model/cache/weather_data.sqlite
```

The cache is not conceptually required, but the remote workflow expects it and training-table builds will be much slower without it.

## Do Not Upload By Default

Do not upload these unless you specifically need to rebuild data products:

```text
weather_reconstruction_artifacts/raw_dem_archive/
weather_reconstruction_artifacts/noaa_year_archive/
weather_reconstruction_artifacts/archive/
weather_reconstruction_artifacts/scratch/
Raw_DEM/
NOAA_Inventory_Sort/NOAA_GHCN_ByYear/
```

Do not upload local Python environments:

```text
.venv/
station-proxy-backend/.venv/
__pycache__/
*.pyc
```

Do not upload generated model outputs unless you need them for comparison:

```text
weather_reconstruction_model/outputs/
```

If you do upload an existing output for comparison, keep it small and intentional. Avoid pushing old multi-GB training tables unless there is a clear reason.

## Suggested Local Rsync Command

From your Mac, run from the project parent directory and replace `YOUR_IDENTIKEY`:

```bash
rsync -av \
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude "station-proxy-backend/.venv/" \
  --exclude "weather_reconstruction_artifacts/" \
  --exclude "weather_reconstruction_model/outputs/" \
  --exclude "Raw_DEM/" \
  --exclude "NOAA_Inventory_Sort/NOAA_GHCN_ByYear/" \
  "colorado-river-basin-weather/" \
  YOUR_IDENTIKEY@login.rc.colorado.edu:/projects/YOUR_IDENTIKEY/crb_weather_project/
```

That command intentionally excludes old artifacts and generated outputs.

## Cache Transfer Option

If you use the broad rsync command above, confirm that this file arrived:

```text
weather_reconstruction_model/cache/weather_data.sqlite
```

If it did not arrive, transfer it explicitly:

```bash
rsync -av \
  "colorado-river-basin-weather/weather_reconstruction_model/cache/weather_data.sqlite" \
  YOUR_IDENTIKEY@login.rc.colorado.edu:/projects/YOUR_IDENTIKEY/crb_weather_project/weather_reconstruction_model/cache/
```

## After Uploading

SSH into Alpine:

```bash
ssh YOUR_IDENTIKEY@login.rc.colorado.edu
```

Load Slurm:

```bash
module load slurm/alpine
```

Copy the project from `/projects` to scratch:

```bash
mkdir -p /scratch/alpine/$USER/crb_weather_runs
rsync -av /projects/$USER/crb_weather_project/ /scratch/alpine/$USER/crb_weather_runs/current/
cd /scratch/alpine/$USER/crb_weather_runs/current
```

Run the environment check:

```bash
python weather_reconstruction_model/scripts/check_remote_environment.py --require-sklearn --check-cache-integrity
```

If that passes, submit the smoke job:

```bash
sbatch remote_jobs/run_smoke.sh
```

## Sanity Checks

Before submitting a serious job, verify:

```bash
pwd
ls
ls NOAA_Inventory_Sort/*_app_ready.csv
ls terrain_data/processed/station_terrain_features.csv
ls weather_reconstruction_model/cache/weather_data.sqlite
ls remote_jobs/run_smoke.sh
```

You should be inside:

```text
/scratch/alpine/$USER/crb_weather_runs/current
```

## Retrieval

After jobs finish, copy outputs back from scratch or projects:

```bash
rsync -av \
  YOUR_IDENTIKEY@login.rc.colorado.edu:/scratch/alpine/YOUR_IDENTIKEY/crb_weather_runs/current/weather_reconstruction_model/outputs/ \
  "colorado-river-basin-weather/weather_reconstruction_model/outputs/"
```

For large result folders, prefer pulling only the specific report/prediction files you need.
