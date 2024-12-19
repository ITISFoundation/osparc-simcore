from typing import Any, Final

from pydantic import NonNegativeFloat

_UNIT_MULTIPLIER: Final[NonNegativeFloat] = 1024.0
TQDM_FILE_OPTIONS: Final[dict[str, Any]] = {
    "unit": "byte",
    "unit_scale": True,
    "unit_divisor": 1024,
    "colour": "yellow",
    "miniters": 1,
}
TQDM_MULTI_FILES_OPTIONS: Final[dict[str, Any]] = TQDM_FILE_OPTIONS | {
    "unit": "file",
    "unit_divisor": 1000,
}


def human_readable_size(size, decimal_places=3):
    human_readable_file_size = float(size)
    unit = "B"
    for t_unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if human_readable_file_size < _UNIT_MULTIPLIER:
            unit = t_unit
            break
        human_readable_file_size /= _UNIT_MULTIPLIER

    return f"{human_readable_file_size:.{decimal_places}f}{unit}"


def compute_tqdm_miniters(byte_size: int) -> float:
    """ensures tqdm minimal iteration is 1 %"""
    return min(byte_size / 100.0, 1.0)
