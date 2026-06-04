from typing import Optional


def to_float(value: object, default: float = 0.0) -> float:
    """Convert a value to float, returning default when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_optional_float(value: object) -> Optional[float]:
    """Convert a value to float, returning None when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
