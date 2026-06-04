# Alpine Slurm Job Scripts

These scripts are templates for running the weather reconstruction workflow on CU Boulder Alpine.

## Safety Boundary

Active or pending Alpine station-holdout jobs may be using the code already
copied to:

```text
/scratch/alpine/$USER/crb_weather_runs/current/weather_reconstruction_model/scripts
/scratch/alpine/$USER/crb_weather_runs/current/remote_jobs
```

Do not rsync, sync, rename, or reorganize that Alpine scratch copy while those
jobs are running. Local edits in this repository are okay, but the scratch copy
should stay frozen until a new version is intentionally validated and synced.

Use them from the project root on Alpine, preferably inside scratch:

```bash
cd /scratch/alpine/$USER/crb_weather_runs/current
sbatch remote_jobs/run_smoke.sh
```

Recommended order:

```text
1. run_smoke.sh
2. run_medium.sh
3. run_wide_medium.sh
4. run_wide_large.sh
5. run_wide_full.sh
```

Do not start with `wide-full`. Let the smaller jobs prove the environment, data paths, and runtime behavior first.

## Script Groups

- Smoke and scale-up checks: `run_smoke.sh`, `run_medium.sh`,
  `run_wide_medium.sh`, `run_wide_large.sh`, `run_wide_full.sh`.
- Paloma table/model export jobs: `run_paloma_build_tables.sh`,
  `run_paloma_export_models.sh`, `run_paloma_export_models_highmem.sh`.
- Paloma station-holdout jobs: `run_paloma_holdout_array.sh`,
  `run_paloma_holdout_array_highmem.sh`,
  `run_paloma_group_holdout_highmem.sh`,
  `run_paloma_merge_holdouts.sh`.
- Result retrieval: `retrieve_alpine_results.sh`.

## Notes

- These scripts use the CPU partition, not GPUs.
- They load `slurm/alpine` and `anaconda`.
- They run the environment checker before model commands.
- They assume the project has already been copied into `/scratch/alpine/$USER/crb_weather_runs/current`.
- If your CURC Python environment has a different activation command, edit the environment section near the top of each script.
- Keep Slurm resource changes explicit in commit messages, because those changes
  affect cost, queue time, and whether a run can complete.
