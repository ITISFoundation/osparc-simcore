from typing import Final

from pydantic import NonNegativeFloat
from tqdm import tqdm

TQDM_EXPORT_OPTIONS: Final[dict] = {
    "unit": "",
    "unit_scale": True,
    "unit_divisor": 1024,
    "colour": "yellow",
    "miniters": 1,
    "ncols": 100,
}


def get_export_progress(total: NonNegativeFloat, *, description: str) -> tqdm:
    return tqdm(**TQDM_EXPORT_OPTIONS, total=total, desc=description)


def set_absolute_progress(pbar: tqdm, *, current_progress: NonNegativeFloat) -> None:
    """used when the progress does not come in chunk by chunk but as the total current value"""
    pbar.n = current_progress
    pbar.refresh()
