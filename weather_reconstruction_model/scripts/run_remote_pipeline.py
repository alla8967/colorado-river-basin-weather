"""Orchestrate named remote reconstruction presets from one command.

Alpine Slurm scripts call this runner so smoke, medium, wide, and holdout workflows share argument construction."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import config
from common.weather_cache import TEMPERATURE_VARIABLES, validate_temperature_variable


DEFAULT_ACTIVE_TABLE = (
    config.GENERAL_TABLE_DIR
    / "option_c_limit97_5_hubs_10_target_neighbors_multiscale_terrain.csv"
)


@dataclass(frozen=True)
class PipelinePreset:
    name: str
    description: str
    build_limit: int | None
    hub_count: int
    target_neighbor_count: int
    target_neighbor_prefilter_count: int
    target_neighbor_max_distance_km: float
    output_stem: str
    train_preset: str
    model: str
    jobs: int
    no_pairwise_output_stem: str | None = None
    always_suffix_variable: bool = False
    forest_trees: int | None = None
    max_depth: int | None = None
    min_samples_leaf: int | None = None


PRESETS = {
    "smoke": PipelinePreset(
        name="smoke",
        description="Fast remote sanity check.",
        build_limit=8,
        hub_count=5,
        target_neighbor_count=3,
        target_neighbor_prefilter_count=30,
        target_neighbor_max_distance_km=300.0,
        output_stem="remote_smoke_8_targets_5_hubs_3_target_neighbors_physical_pairwise_selection",
        train_preset="quick",
        model="random-forest",
        jobs=1,
    ),
    "medium": PipelinePreset(
        name="medium",
        description="Meaningful 97-target run using the current Option C shape.",
        build_limit=97,
        hub_count=5,
        target_neighbor_count=10,
        target_neighbor_prefilter_count=100,
        target_neighbor_max_distance_km=300.0,
        output_stem="remote_medium_97_targets_5_hubs_10_target_neighbors_physical_pairwise_selection",
        train_preset="standard",
        model="random-forest",
        jobs=-1,
    ),
    "full": PipelinePreset(
        name="full",
        description="Large remote run across all currently listed target stations.",
        build_limit=0,
        hub_count=5,
        target_neighbor_count=10,
        target_neighbor_prefilter_count=200,
        target_neighbor_max_distance_km=500.0,
        output_stem="remote_full_all_targets_5_hubs_10_target_neighbors_physical_pairwise_selection",
        train_preset="heavy",
        model="random-forest",
        jobs=-1,
    ),
    "paloma-full": PipelinePreset(
        name="paloma-full",
        description=(
            "Official Paloma v1 full-table build across every currently eligible "
            "target station, using physical selection without pairwise skill."
        ),
        build_limit=0,
        hub_count=5,
        target_neighbor_count=10,
        target_neighbor_prefilter_count=200,
        target_neighbor_max_distance_km=500.0,
        output_stem="paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_pairwise_selection",
        no_pairwise_output_stem="paloma_v1_full_all_targets_5_hubs_10_target_neighbors_physical_selection_no_pairwise",
        always_suffix_variable=True,
        train_preset="heavy",
        model="random-forest",
        jobs=-1,
        forest_trees=300,
        max_depth=20,
        min_samples_leaf=5,
    ),
    "wide-medium": PipelinePreset(
        name="wide-medium",
        description=(
            "Remote experiment with more stations and a wider predictor set: "
            "200 targets, 10 hubs, and 20 target-neighbor stations."
        ),
        build_limit=200,
        hub_count=10,
        target_neighbor_count=20,
        target_neighbor_prefilter_count=200,
        target_neighbor_max_distance_km=500.0,
        output_stem="remote_wide_medium_200_targets_10_hubs_20_target_neighbors_physical_pairwise_selection",
        train_preset="standard",
        model="random-forest",
        jobs=-1,
    ),
    "wide-large": PipelinePreset(
        name="wide-large",
        description=(
            "Larger remote experiment with 400 targets, 15 hubs, and "
            "30 target-neighbor stations."
        ),
        build_limit=400,
        hub_count=15,
        target_neighbor_count=30,
        target_neighbor_prefilter_count=300,
        target_neighbor_max_distance_km=650.0,
        output_stem="remote_wide_large_400_targets_15_hubs_30_target_neighbors_physical_pairwise_selection",
        train_preset="heavy",
        model="random-forest",
        jobs=-1,
    ),
    "wide-full": PipelinePreset(
        name="wide-full",
        description=(
            "Maximum planned remote experiment across all target candidates with "
            "20 hubs and 40 target-neighbor stations."
        ),
        build_limit=808,
        hub_count=20,
        target_neighbor_count=40,
        target_neighbor_prefilter_count=400,
        target_neighbor_max_distance_km=800.0,
        output_stem="remote_wide_full_all_targets_20_hubs_40_target_neighbors_physical_pairwise_selection",
        train_preset="heavy",
        model="random-forest",
        jobs=-1,
        forest_trees=400,
        max_depth=22,
        min_samples_leaf=4,
    ),
    "holdout-full": PipelinePreset(
        name="holdout-full",
        description="Station-holdout validation against an existing general training table.",
        build_limit=None,
        hub_count=5,
        target_neighbor_count=10,
        target_neighbor_prefilter_count=100,
        target_neighbor_max_distance_km=300.0,
        output_stem="remote_station_holdout_offset_random_forest",
        train_preset="quick",
        model="random-forest",
        jobs=-1,
        forest_trees=80,
        max_depth=14,
        min_samples_leaf=10,
    ),
}


def display_command(command: list[str]) -> str:
    return " ".join(command)


def run_command(command: list[str], dry_run: bool) -> None:
    print()
    print(display_command(command))
    if dry_run:
        return

    subprocess.run(command, cwd=config.PROJECT_DIR, check=True)


def output_stem_for_run(
    preset: PipelinePreset,
    use_pairwise_skill: bool = True,
    variable: str = "tavg",
    output_stem_override: str | None = None,
) -> str:
    variable = validate_temperature_variable(variable)

    if output_stem_override:
        return output_stem_override

    if use_pairwise_skill:
        output_stem = preset.output_stem
    elif preset.no_pairwise_output_stem is not None:
        output_stem = preset.no_pairwise_output_stem
    else:
        output_stem = preset.output_stem.replace(
            "_physical_pairwise_selection",
            "_physical_selection_no_pairwise_ablation",
        )

    if preset.always_suffix_variable or variable != "tavg":
        output_stem = f"{output_stem}_{variable}"

    return output_stem


def build_table_command(
    preset: PipelinePreset,
    use_pairwise_skill: bool = True,
    variable: str = "tavg",
    output_stem_override: str | None = None,
) -> list[str]:
    variable = validate_temperature_variable(variable)

    if preset.build_limit is None:
        raise ValueError(f"Preset {preset.name} does not build a general training table.")

    command = [
        sys.executable,
        "weather_reconstruction_model/scripts/build_general_training_table.py",
        "--limit",
        str(preset.build_limit),
        "--hub-count",
        str(preset.hub_count),
        "--target-neighbor-count",
        str(preset.target_neighbor_count),
        "--target-neighbor-prefilter-count",
        str(preset.target_neighbor_prefilter_count),
        "--target-neighbor-max-distance-km",
        str(preset.target_neighbor_max_distance_km),
        "--use-cache",
        "--variable",
        variable,
        "--output-stem",
        output_stem_for_run(
            preset,
            use_pairwise_skill,
            variable,
            output_stem_override,
        ),
    ]

    if use_pairwise_skill:
        command.extend([
            "--pairwise-skill-file",
            str(pairwise_skill_file_for_preset(preset, variable)),
        ])
    else:
        command.append("--disable-pairwise-skill")

    return command


def pairwise_skill_file_for_preset(
    preset: PipelinePreset,
    variable: str = "tavg",
) -> Path:
    variable = validate_temperature_variable(variable)
    output_stem = output_stem_for_run(
        preset,
        use_pairwise_skill=True,
        variable=variable,
    )
    return config.CACHE_DIR / f"{output_stem}_pairwise_skill_train_through_{config.DEFAULT_TRAIN_END_YEAR}.csv"


def build_pairwise_skill_command(
    preset: PipelinePreset,
    variable: str = "tavg",
) -> list[str]:
    variable = validate_temperature_variable(variable)

    if preset.build_limit is None:
        raise ValueError(f"Preset {preset.name} does not build pairwise skill features.")

    return [
        sys.executable,
        "weather_reconstruction_model/scripts/build_pairwise_station_skill_features.py",
        "--target-limit",
        str(preset.build_limit),
        "--target-neighbor-prefilter-count",
        str(preset.target_neighbor_prefilter_count),
        "--target-neighbor-max-distance-km",
        str(preset.target_neighbor_max_distance_km),
        "--train-end-year",
        str(config.DEFAULT_TRAIN_END_YEAR),
        "--variable",
        variable,
        "--output-file",
        str(pairwise_skill_file_for_preset(preset, variable)),
    ]


def train_table_command(
    preset: PipelinePreset,
    general_table: Path,
    worst_count: int,
    variable: str = "tavg",
) -> list[str]:
    variable = validate_temperature_variable(variable)
    command = [
        sys.executable,
        "weather_reconstruction_model/scripts/train_tree_temperature_model.py",
        str(general_table),
        "--preset",
        preset.train_preset,
        "--model",
        preset.model,
        "--jobs",
        str(preset.jobs),
        "--worst-count",
        str(worst_count),
        "--variable",
        variable,
        "--predict-offset-from-baseline",
    ]

    if preset.forest_trees is not None:
        command.extend(["--forest-trees", str(preset.forest_trees)])
    if preset.max_depth is not None:
        command.extend(["--max-depth", str(preset.max_depth)])
    if preset.min_samples_leaf is not None:
        command.extend(["--min-samples-leaf", str(preset.min_samples_leaf)])

    return command


def holdout_command(
    preset: PipelinePreset,
    general_table: Path,
    resume: bool,
    variable: str = "tavg",
    station_list: Path | None = None,
    output_stem_override: str | None = None,
) -> list[str]:
    variable = validate_temperature_variable(variable)
    command = [
        sys.executable,
        "weather_reconstruction_model/scripts/train_station_holdout_model.py",
        str(general_table),
        "--predict-offset-from-baseline",
        "--variable",
        variable,
        "--jobs",
        str(preset.jobs),
        "--output-stem",
        output_stem_override or preset.output_stem,
    ]

    if station_list is not None:
        command.extend(["--station-list", str(station_list)])
    if preset.forest_trees is not None:
        command.extend(["--forest-trees", str(preset.forest_trees)])
    if preset.max_depth is not None:
        command.extend(["--max-depth", str(preset.max_depth)])
    if preset.min_samples_leaf is not None:
        command.extend(["--min-samples-leaf", str(preset.min_samples_leaf)])
    if resume:
        command.append("--resume")

    return command


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run remote-friendly weather reconstruction pipeline presets."
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        required=True,
        help="Pipeline preset to run.",
    )
    parser.add_argument(
        "--general-table",
        type=Path,
        default=None,
        help=(
            "Existing general training table. Required for holdout-full unless the "
            "current active table exists. Optional for train-only use."
        ),
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip general table building and train from --general-table.",
    )
    parser.add_argument(
        "--skip-pairwise",
        action="store_true",
        help="Skip pairwise skill feature generation before table building.",
    )
    parser.add_argument(
        "--only-build",
        action="store_true",
        help="Build the general table but do not train a model.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them.",
    )
    parser.add_argument(
        "--worst-count",
        type=int,
        default=12,
        help="Number of worst stations to print during model training.",
    )
    parser.add_argument(
        "--variable",
        choices=sorted(TEMPERATURE_VARIABLES),
        default="tavg",
        help="Daily temperature variable to build and train.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume mode for holdout-full.",
    )
    parser.add_argument(
        "--output-stem",
        default=None,
        help=(
            "Optional exact output filename stem for the general table build, "
            "or holdout output stem when using holdout-full."
        ),
    )
    parser.add_argument(
        "--station-list",
        type=Path,
        default=None,
        help="Optional station-list CSV for holdout-full.",
    )
    return parser.parse_args()


def resolve_general_table(
    arguments: argparse.Namespace,
    preset: PipelinePreset,
    use_pairwise_skill: bool = True,
    variable: str = "tavg",
) -> Path:
    variable = validate_temperature_variable(variable)

    if arguments.general_table is not None:
        return arguments.general_table

    output_stem = getattr(arguments, "output_stem", None)
    if output_stem is not None and preset.name != "holdout-full":
        return config.GENERAL_TABLE_DIR / f"{output_stem}.csv"

    if preset.name == "holdout-full":
        return DEFAULT_ACTIVE_TABLE

    return config.GENERAL_TABLE_DIR / f"{output_stem_for_run(preset, use_pairwise_skill, variable)}.csv"


def main() -> None:
    arguments = parse_arguments()
    preset = PRESETS[arguments.preset]
    variable = validate_temperature_variable(arguments.variable)
    use_pairwise_skill = not arguments.skip_pairwise
    general_table = resolve_general_table(
        arguments,
        preset,
        use_pairwise_skill=use_pairwise_skill,
        variable=variable,
    )

    print("Remote Pipeline Runner")
    print("======================")
    print(f"Preset: {preset.name}")
    print(preset.description)
    print(f"Project root: {config.PROJECT_DIR}")
    print(f"General table: {general_table}")
    print(f"Temperature variable: {variable}")
    if preset.build_limit is not None:
        if use_pairwise_skill:
            print(f"Pairwise skill file: {pairwise_skill_file_for_preset(preset, variable)}")
        else:
            print("Pairwise skill: disabled")

    if arguments.preset == "holdout-full":
        if not general_table.exists() and not arguments.dry_run:
            raise FileNotFoundError(
                f"Holdout preset requires an existing general table: {general_table}"
            )
        command = holdout_command(
            preset,
            general_table,
            resume=not arguments.no_resume,
            variable=variable,
            station_list=arguments.station_list,
            output_stem_override=arguments.output_stem,
        )
        run_command(command, arguments.dry_run)
        return

    if not arguments.skip_build:
        if use_pairwise_skill:
            command = build_pairwise_skill_command(preset, variable)
            run_command(command, arguments.dry_run)
        command = build_table_command(
            preset,
            use_pairwise_skill=use_pairwise_skill,
            variable=variable,
            output_stem_override=arguments.output_stem,
        )
        run_command(command, arguments.dry_run)

    if arguments.only_build:
        return

    if arguments.skip_build and not general_table.exists() and not arguments.dry_run:
        raise FileNotFoundError(f"General table does not exist: {general_table}")

    command = train_table_command(
        preset,
        general_table,
        arguments.worst_count,
        variable,
    )
    run_command(command, arguments.dry_run)


if __name__ == "__main__":
    main()
