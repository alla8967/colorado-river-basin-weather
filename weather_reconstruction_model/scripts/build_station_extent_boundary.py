from __future__ import annotations

import argparse
from pathlib import Path

import config
from common.json_utils import write_json_file
from common.reliability_surface import build_station_extent_boundary_geojson


DEFAULT_OUTPUT_FILE = (
    config.PROJECT_DIR
    / "weather_reconstruction_model"
    / "inputs"
    / "colorado_river_basin_boundary.geojson"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the reliability-map rectangle boundary from the furthest "
            "north/south/east/west station coordinates plus padding in each direction."
        )
    )
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--target-candidates", type=Path, default=config.TARGET_CANDIDATE_FILE)
    parser.add_argument("--hub-candidates", type=Path, default=config.HUB_CANDIDATE_FILE)
    parser.add_argument("--terrain-features", type=Path, default=config.TERRAIN_FEATURE_FILE)
    parser.add_argument("--padding-km", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    boundary = build_station_extent_boundary_geojson(
        coordinate_files=[
            args.target_candidates,
            args.hub_candidates,
            args.terrain_features,
        ],
        padding_km=args.padding_km,
    )
    write_json_file(args.output_file, boundary)
    properties = boundary["properties"]
    print(f"Boundary: {args.output_file}")
    print(f"Stations: {properties['stationCount']}")
    print(f"Padding: {properties['paddingKm']} km")
    print(f"Padded bounds: {properties['paddedBounds']}")


if __name__ == "__main__":
    main()
