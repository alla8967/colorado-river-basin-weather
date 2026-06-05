"""Provide small CSV reading, writing, and inspection helpers for scripts.

Centralizing these wrappers keeps command-line entry points focused on workflow logic."""

from pathlib import Path
import csv
from typing import Mapping, Sequence


CsvRow = dict[str, str]
WritableCsvRow = Mapping[str, object]
Fieldnames = Sequence[str]


def read_csv_rows(file_path: Path) -> list[CsvRow]:
    """Read a CSV file into a list of dictionaries."""
    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def read_csv_fieldnames(file_path: Path) -> list[str]:
    """Read the header row from a CSV file."""
    with file_path.open("r", newline="") as file:
        reader = csv.reader(file)
        return next(reader)


def count_csv_rows(file_path: Path) -> int:
    """Count data rows in a CSV file, excluding the header row."""
    with file_path.open("r", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


def write_csv_rows(
    file_path: Path,
    rows: Sequence[WritableCsvRow],
    fieldnames: Fieldnames,
) -> None:
    """Write dictionary rows to a CSV file, creating the parent folder if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_csv_rows_inferred(
    file_path: Path,
    rows: Sequence[WritableCsvRow],
) -> None:
    """Write rows to CSV using the first row's keys as fieldnames."""
    if not rows:
        raise ValueError("Cannot infer CSV fieldnames from an empty row sequence.")

    write_csv_rows(file_path, rows, list(rows[0].keys()))
