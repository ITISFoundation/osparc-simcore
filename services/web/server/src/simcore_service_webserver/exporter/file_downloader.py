import logging
from pathlib import Path

from aiohttp.web import Application
from parfive.downloader import Downloader

from .exceptions import ExporterException
from .settings import get_settings
from .utils import makedirs

log = logging.getLogger(__name__)


class ParallelDownloader:
    def __init__(self):
        self.downloader = Downloader(
            progress=False, file_progress=False, notebook=False, overwrite=True
        )
        self.total_files_added = 0

    async def append_file(self, link: str, download_path: Path) -> None:
        await makedirs(download_path.parent, exist_ok=True)
        self.downloader.enqueue_file(
            url=link, path=download_path.parent, filename=download_path.name
        )
        self.total_files_added += 1

    async def download_files(self, app: Application) -> None:
        """starts the download and waits for all files to finish"""
        exporter_settings = get_settings(app)
        assert (  # nosec
            exporter_settings is None
        ), "this call was not expected with a disabled plugin"  # nosec

        results = await self.downloader.run_download(
            timeouts={
                "total": exporter_settings.EXPORTER_DOWNLOADER_MAX_TIMEOUT_SECONDS,
                "sock_read": 90,  # default as in parfive code
            }
        )

        log.debug("Download %s using %s", f"{results=}", f"{self.downloader=}")
        if len(results) != self.total_files_added or len(results.errors) > 0:
            message = f"Not all files were downloaded: {results.errors=}"
            log.error(message)
            raise ExporterException(message)
