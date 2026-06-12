"""Build the README portfolio figure from row-locked holdout artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPARISON_CSV = (
    PROJECT_ROOT
    / "weather_reconstruction_model"
    / "outputs"
    / "reports"
    / "comparisons"
    / "paloma_v1_tavg_holdout_baseline_comparison_station_comparison.csv"
)
SUMMARY_JSON = (
    PROJECT_ROOT
    / "weather_reconstruction_model"
    / "outputs"
    / "reports"
    / "comparisons"
    / "paloma_v1_tavg_holdout_baseline_comparison_summary.json"
)
TARGET_COORDS_CSV = PROJECT_ROOT / "NOAA_Inventory_Sort" / "target_station_candidates.csv"
OUTPUT_PNG = PROJECT_ROOT / "docs" / "assets" / "baseline_comparison.png"

EXPECTED = {
    "station_count": 739,
    "row_count": 416_892,
    "model_mean_station_mae": 2.683792674009441,
    "idw_hubs_mean_station_mae": 4.993924955232766,
    "nearest_hub_mean_station_mae": 5.577332808077571,
    "model_better_than_idw_count": 588,
    "model_better_than_nearest_count": 631,
    "model_strict_pass_count": 52,
    "idw_hubs_strict_pass_count": 9,
    "nearest_hub_strict_pass_count": 8,
    "model_median_station_mae": 2.4855387523629484,
    "model_p90_station_mae": 3.9965086206896574,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-csv", type=Path, default=COMPARISON_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--target-coords-csv", type=Path, default=TARGET_COORDS_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_PNG)
    return parser.parse_args()


def require_matplotlib():
    os.environ.setdefault(
        "MPLCONFIGDIR",
        str(Path(tempfile.gettempdir()) / "crb_matplotlib_cache"),
    )
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import colors
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required to rebuild this figure. Install it with: "
            "python -m pip install -e \".[viz]\""
        ) from exc

    return plt, colors


def load_summary(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        summary = json.load(handle)

    for key, expected in EXPECTED.items():
        actual = summary.get(key)
        if isinstance(expected, int):
            if actual != expected:
                raise ValueError(f"{key} changed: expected {expected}, found {actual}")
            continue

        if abs(float(actual) - expected) > 1e-9:
            raise ValueError(f"{key} changed: expected {expected}, found {actual}")

    return summary


def load_station_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != EXPECTED["station_count"]:
        raise ValueError(
            f"station comparison row count changed: expected "
            f"{EXPECTED['station_count']}, found {len(rows)}"
        )

    return rows


def load_coordinates(path: Path) -> dict[str, tuple[float, float]]:
    coordinates: dict[str, tuple[float, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            station_id = row.get("station_id", "")
            if not station_id:
                continue

            try:
                coordinates[station_id] = (float(row["longitude"]), float(row["latitude"]))
            except (KeyError, TypeError, ValueError):
                continue

    return coordinates


def joined_station_points(
    station_rows: list[dict],
    coordinates: dict[str, tuple[float, float]],
) -> tuple[list[dict], list[str]]:
    joined = []
    missing = []

    for row in station_rows:
        station_id = row["target_station_id"]
        coordinate = coordinates.get(station_id)
        if coordinate is None:
            missing.append(station_id)
            continue

        longitude, latitude = coordinate
        joined.append(
            {
                "station_id": station_id,
                "longitude": longitude,
                "latitude": latitude,
                "model_mae": float(row["model_mae"]),
            }
        )

    return joined, missing


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)


def draw_bar_panel(ax) -> None:
    labels = ["Model", "IDW\n5-hub", "Nearest\nhub"]
    values = [2.68, 4.99, 5.58]
    colors = ["#1b9e77", "#d95f02", "#4b5563"]
    bars = ax.bar(labels, values, color=colors, width=0.62)

    ax.set_title("Mean Station MAE", loc="left", fontsize=15, fontweight="bold")
    ax.set_ylabel("Temperature error (F)")
    ax.set_ylim(0, 6.3)
    style_axes(ax)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.12,
            f"{value:.2f} F",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#111827",
        )

    ax.text(
        0.02,
        0.93,
        "46% lower than IDW",
        transform=ax.transAxes,
        fontsize=11,
        color="#065f46",
        fontweight="bold",
    )


def draw_scatter_panel(fig, ax, joined: list[dict], colors_module) -> None:
    longitudes = [point["longitude"] for point in joined]
    latitudes = [point["latitude"] for point in joined]
    model_mae = [point["model_mae"] for point in joined]
    norm = colors_module.Normalize(vmin=1.0, vmax=6.0)

    scatter = ax.scatter(
        longitudes,
        latitudes,
        c=model_mae,
        cmap="viridis",
        norm=norm,
        s=26,
        linewidth=0.25,
        edgecolor="#ffffff",
        alpha=0.92,
    )

    ax.set_title("Held-Out Stations by Model MAE", loc="left", fontsize=15, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#cbd5e1")

    cbar = fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Model MAE (F)")


def draw_distribution_panel(ax, station_rows: list[dict]) -> None:
    values = [float(row["model_mae"]) for row in station_rows]
    ax.hist(values, bins=24, color="#1b9e77", edgecolor="#ffffff")
    ax.axvline(2.49, color="#111827", linewidth=1.6, label="Median 2.49 F")
    ax.axvline(4.00, color="#d95f02", linewidth=1.6, label="P90 4.00 F")
    ax.set_title("Model MAE Distribution", loc="left", fontsize=15, fontweight="bold")
    ax.set_xlabel("Station MAE (F)")
    ax.set_ylabel("Held-out stations")
    ax.legend(frameon=False, loc="upper right")
    style_axes(ax)


def build_figure(args: argparse.Namespace) -> None:
    plt, colors_module = require_matplotlib()
    summary = load_summary(args.summary_json)
    station_rows = load_station_rows(args.comparison_csv)
    coordinates = load_coordinates(args.target_coords_csv)
    joined, missing = joined_station_points(station_rows, coordinates)

    figure = plt.figure(figsize=(12, 6.8), dpi=150)
    grid = figure.add_gridspec(2, 2, height_ratios=[12, 1.5], width_ratios=[0.85, 1.25])
    left_ax = figure.add_subplot(grid[0, 0])
    right_ax = figure.add_subplot(grid[0, 1])
    caption_ax = figure.add_subplot(grid[1, :])
    caption_ax.axis("off")

    draw_bar_panel(left_ax)
    if not missing and len(joined) == summary["station_count"]:
        draw_scatter_panel(figure, right_ax, joined, colors_module)
        join_note = "Station coordinates joined cleanly from target_station_candidates.csv."
    else:
        draw_distribution_panel(right_ax, station_rows)
        join_note = (
            f"Coordinate join incomplete; used distribution panel instead "
            f"({len(missing)} missing station ids)."
        )

    figure.suptitle(
        "Temperature Reconstruction Beats Simple Station Baselines",
        x=0.04,
        y=0.985,
        ha="left",
        fontsize=19,
        fontweight="bold",
        color="#111827",
    )
    caption = (
        "739 held-out stations, row-locked baselines. "
        "Model mean station MAE: 2.68 F; IDW 5-hub: 4.99 F; nearest hub: 5.58 F. "
        "Model beats IDW at 588/739 stations (80%) and nearest hub at 631/739 (85%). "
        f"{join_note}"
    )
    caption_ax.text(0.0, 0.75, caption, ha="left", va="top", fontsize=10.5, color="#374151", wrap=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(args.output, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def main() -> None:
    build_figure(parse_args())


if __name__ == "__main__":
    main()
