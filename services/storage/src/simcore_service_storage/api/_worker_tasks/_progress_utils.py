from typing import Final

from models_library.progress_bar import ProgressReport
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


def get_tqdm_progress(total: NonNegativeFloat, *, description: str) -> tqdm:
    return tqdm(**TQDM_EXPORT_OPTIONS, total=total, desc=description)


def set_tqdm_absolute_progress(pbar: tqdm, report: ProgressReport) -> None:
    """used when the progress does not come in chunk by chunk but as the total current value"""
    pbar.n = report.actual_value
    pbar.refresh()
