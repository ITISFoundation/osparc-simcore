# pylint ignore=arguments-differ

from abc import abstractmethod
from pathlib import Path


class BaseFormatter:
    def __init__(self, version: str, root_folder: Path):
        self.version: str = version
        self.root_folder: Path = root_folder

    @abstractmethod
    async def format_export_directory(self, *args, **kwargs):
        """Creates the output format given the current version
        and saves all data to the relative path."""

    @abstractmethod
    async def validate_and_import_directory(self, *args, **kwargs):
        """Validates an uploaded unzipped project and will try
        to import all the data inside the platfrom"""
