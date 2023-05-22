# pylint ignore=arguments-differ

from abc import abstractmethod
from pathlib import Path

from aiohttp import web


class BaseFormatter:
    def __init__(self, version: str, root_folder: Path):
        self.version: str = version
        self.root_folder: Path = root_folder

    @abstractmethod
    async def format_export_directory(
        self, app: web.Application, project_id: str, user_id: int, **kwargs
    ) -> None:
        """Creates the output format given the current version
        and saves all data to the relative path."""
