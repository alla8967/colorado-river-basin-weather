# Training Pipeline Helpers

This package contains reusable pipeline logic for selecting stations, building
training rows, choosing model features, and preventing station-holdout leakage.

## What Belongs Here

Use `pipeline/` for behavior that is specific to model-training workflows:

- station and neighbor selection,
- feature-selection modes,
- training-table row and fieldname construction,
- feature/label extraction for model trainers,
- station-holdout row filtering.

Command-line scripts should stay focused on arguments, paths, and orchestration;
reusable training logic should move here.

