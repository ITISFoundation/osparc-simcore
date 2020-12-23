from typing import Dict
from pathlib import Path

from aiohttp import web


from .base_formatter import BaseFormatter
from .models import Manifest
from .formatter_v1 import FormatterV1


# maps manifest version to available formatters
_FORMATTERS_MAPPINGS: Dict[str, BaseFormatter] = {"1": FormatterV1}


async def validate_manifest(unzipped_root_folder: Path) -> BaseFormatter:
    """Checks if the file contains a manifest and will return a formatter based on the version"""

    manifest_from_file = await Manifest.model_from_file(root_dir=unzipped_root_folder)

    formatter_cls: BaseFormatter = _FORMATTERS_MAPPINGS[manifest_from_file.version]
    return formatter_cls(root_folder=unzipped_root_folder)