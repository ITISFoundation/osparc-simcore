import logging

from parfive.downloader import Downloader
from pathlib import Path

from aiofiles import os as aiofiles_os

from .file_response import makedirs

log = logging.getLogger(__name__)


class ParallelDownloader:
    def __init__(self):
        self.downloader = Downloader(
            progress=False, file_progress=False, notebook=False, overwrite=True
        )

    async def append_file(self, link: str, download_path: Path):
        await makedirs(download_path.parent, exist_ok=True)
        self.downloader.enqueue_file(
            url=link, path=download_path.parent, filename=download_path.name
        )

    async def download_files(self):
        """starts the download and waits for all files to finish"""

        # run this async
        wrapped_function = aiofiles_os.wrap(self.downloader.download)
        results = await wrapped_function()
        log.info("Download results %s", results)
        # TODO: check if all files have been downloaded
