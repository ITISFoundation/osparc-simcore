# pylint ignore=arguments-differ

import logging

from aiohttp import web
from abc import abstractmethod
from typing import Dict
from pathlib import Path

from .serialize import loads

log = logging.getLogger(__name__)


class BaseImporter:
    def __init__(self, version: str, root_folder: Path):
        self.version: str = version
        self.root_folder: Path = root_folder

    @abstractmethod
    async def start_import(self, *args, **kwargs):
        """Customize this based on the rest"""


class ImporterV1(BaseImporter):
    async def start_import(self, *args, **kwargs):
        projects_path = self.root_folder / "project.yaml"
        storage_path = self.root_folder / "storage"

        if not projects_path.is_file():
            raise web.HTTPException(
                reason=f"File {str(projects_path)} was not found in archive"
            )

        if not storage_path.is_dir():
            raise web.HTTPException(
                reason=f"Directory {str(storage_path)} was not found in archive"
            )

        project_data = loads(projects_path.read_text())
        log.info("Loaded project data: %s", project_data)


SUPPORTED_IMPORTERS_FROM_VERSION: Dict[str, BaseImporter] = {"1": ImporterV1}
