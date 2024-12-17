import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from ..progress_bar import ProgressBarData

_logger = logging.getLogger(__name__)


async def archive_dir(
    dir_to_compress: Path,
    destination: Path,
    *,
    compress: bool,
    store_relative_path: bool,
    exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData | None = None,
) -> None:
    pass


async def unarchive_dir(
    archive_to_extract: Path,
    destination_folder: Path,
    *,
    max_workers: int = 0,
    progress_bar: ProgressBarData | None = None,
    log_cb: Callable[[str], Awaitable[None]] | None = None,
) -> set[Path]:
    # NOTE: maintained here conserve the interface
    _ = max_workers  # no longer used

    return set()
