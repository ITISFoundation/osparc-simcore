from typing import Final

from pydantic import ByteSize, NonNegativeInt

TQDM_FILE_OPTIONS: Final[dict] = {
    "unit": "byte",
    "unit_scale": True,
    "unit_divisor": 1024,
    "colour": "yellow",
    "miniters": 1,
}
TQDM_MULTI_FILES_OPTIONS: Final[dict] = TQDM_FILE_OPTIONS | {
    "unit": "file",
    "unit_divisor": 1000,
}


def human_readable_size(size: NonNegativeInt) -> str:
    return ByteSize(size).human_readable()


def compute_tqdm_miniters(byte_size: int) -> float:
    """ensures tqdm minimal iteration is 1 %"""
    return min(byte_size / 100.0, 1.0)
