"""Test remote pipeline command construction for temperature variables and presets.

This prevents Slurm wrappers from drifting away from the Python runner contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import config
import run_remote_pipeline as remote_pipeline


def option_after(command: list[str], option: str) -> str:
    return command[command.index(option) + 1]


def test_output_stems_include_variable_and_pairwise_mode() -> None:
    preset = remote_pipeline.PRESETS["medium"]

    assert remote_pipeline.output_stem_for_run(
        preset,
        use_pairwise_skill=True,
        variable="tavg",
    ) == preset.output_stem
    assert remote_pipeline.output_stem_for_run(
        preset,
        use_pairwise_skill=False,
        variable="tmin",
    ).endswith("_physical_selection_no_pairwise_ablation_tmin")


def test_build_and_train_commands_pass_variable() -> None:
    preset = remote_pipeline.PRESETS["medium"]
    table_command = remote_pipeline.build_table_command(
        preset,
        use_pairwise_skill=False,
        variable="tmin",
    )
    train_command = remote_pipeline.train_table_command(
        preset,
        Path("table.csv"),
        worst_count=7,
        variable="tmin",
    )

    assert option_after(table_command, "--variable") == "tmin"
    assert "--disable-pairwise-skill" in table_command
    assert option_after(table_command, "--output-stem").endswith(
        "_physical_selection_no_pairwise_ablation_tmin"
    )
    assert option_after(train_command, "--variable") == "tmin"
    assert option_after(train_command, "--worst-count") == "7"


def test_pairwise_command_and_file_are_variable_specific() -> None:
    preset = remote_pipeline.PRESETS["smoke"]
    pairwise_file = remote_pipeline.pairwise_skill_file_for_preset(
        preset,
        variable="tmax",
    )
    pairwise_command = remote_pipeline.build_pairwise_skill_command(
        preset,
        variable="tmax",
    )

    assert pairwise_file.name.endswith(
        f"_tmax_pairwise_skill_train_through_{config.DEFAULT_TRAIN_END_YEAR}.csv"
    )
    assert option_after(pairwise_command, "--variable") == "tmax"
    assert option_after(pairwise_command, "--output-file") == str(pairwise_file)


def test_resolve_general_table_uses_variable_specific_stem() -> None:
    preset = remote_pipeline.PRESETS["wide-medium"]
    arguments = argparse.Namespace(general_table=None)
    general_table = remote_pipeline.resolve_general_table(
        arguments,
        preset,
        use_pairwise_skill=False,
        variable="tmin",
    )

    assert general_table.parent == config.GENERAL_TABLE_DIR
    assert general_table.name.endswith("_physical_selection_no_pairwise_ablation_tmin.csv")


def test_paloma_full_uses_official_all_target_variable_stem() -> None:
    preset = remote_pipeline.PRESETS["paloma-full"]
    output_stem = remote_pipeline.output_stem_for_run(
        preset,
        use_pairwise_skill=False,
        variable="tavg",
    )
    table_command = remote_pipeline.build_table_command(
        preset,
        use_pairwise_skill=False,
        variable="tmax",
    )

    assert preset.build_limit == 0
    assert output_stem == (
        "paloma_v1_full_all_targets_5_hubs_10_target_neighbors_"
        "physical_selection_no_pairwise_tavg"
    )
    assert option_after(table_command, "--limit") == "0"
    assert option_after(table_command, "--output-stem") == (
        "paloma_v1_full_all_targets_5_hubs_10_target_neighbors_"
        "physical_selection_no_pairwise_tmax"
    )


def test_holdout_command_passes_variable_and_station_list() -> None:
    preset = remote_pipeline.PRESETS["holdout-full"]
    command = remote_pipeline.holdout_command(
        preset,
        Path("table.csv"),
        resume=True,
        variable="tmin",
        station_list=Path("chunk_001.csv"),
        output_stem_override="paloma_v1_tmin_holdout_chunk_001",
    )

    assert option_after(command, "--variable") == "tmin"
    assert option_after(command, "--station-list") == "chunk_001.csv"
    assert option_after(command, "--output-stem") == "paloma_v1_tmin_holdout_chunk_001"
    assert "--resume" in command


def test_output_stem_override_is_exact() -> None:
    preset = remote_pipeline.PRESETS["paloma-full"]

    assert remote_pipeline.output_stem_for_run(
        preset,
        use_pairwise_skill=False,
        variable="tmax",
        output_stem_override="custom_exact_stem",
    ) == "custom_exact_stem"


def main() -> None:
    test_output_stems_include_variable_and_pairwise_mode()
    test_build_and_train_commands_pass_variable()
    test_pairwise_command_and_file_are_variable_specific()
    test_resolve_general_table_uses_variable_specific_stem()
    test_paloma_full_uses_official_all_target_variable_stem()
    test_holdout_command_passes_variable_and_station_list()
    test_output_stem_override_is_exact()
    print("remote pipeline variable tests passed")


if __name__ == "__main__":
    main()
