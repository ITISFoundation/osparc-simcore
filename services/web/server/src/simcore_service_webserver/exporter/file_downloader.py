import logging
from pathlib import Path

import parfive
from aiofiles import os as aiofiles_os
from parfive.downloader import Downloader

from .exceptions import ExporterException
from .utils import makedirs

log = logging.getLogger(__name__)

if parfive.__version__ != "1.0.2":
    raise RuntimeError(
        "Parfive was upgraded, please make sure this version supports "
        "aiofiles otherwise it will block the main loop while downloading files. "
        "If such condition is not met please do not upgrade! "
        "A PR to parfive will be submitted by GitHK and this should be no longer required."
    )


class ParallelDownloader:
    def __init__(self):
        self.downloader = Downloader(
            progress=False, file_progress=False, notebook=False, overwrite=True
        )
        self.total_files_added = 0

    async def append_file(self, link: str, download_path: Path):
        await makedirs(download_path.parent, exist_ok=True)
        self.downloader.enqueue_file(
            url=link, path=download_path.parent, filename=download_path.name
        )
        self.total_files_added += 1

    async def download_files(self):
        """starts the download and waits for all files to finish"""

        # run this async, newer versions do not require this trick
        wrapped_function = aiofiles_os.wrap(self.downloader.download)
        results = await wrapped_function()
        log.debug("Download results %s", results)

        if len(results) != self.total_files_added:
            raise ExporterException(
                "Not all files were downloaded. Please check the logs above."
            )
