from typing import Dict
from pathlib import Path

from aiohttp import web


from .base import BaseFormatter
from .v1 import FormatterV1
from ..serialize import loads

# maps manifest version to available formatters
_FORMATTERS_MAPPINGS: Dict[str, BaseFormatter] = {"1": FormatterV1}


async def validate_manifest(unzipped_root_folder: Path) -> BaseFormatter:
    """Checks if the file contains a manifest and will return a formatter based on the version"""

    manifest = unzipped_root_folder / "manifest.yaml"

    if not manifest.is_file():
        raise web.HTTPException(
            reason=f"Expected a manifest.yaml file was not found in project {unzipped_root_folder}"
        )

    manifest_data = loads(manifest.read_text())
    version = manifest_data.get("version", None)
    if version not in _FORMATTERS_MAPPINGS:
        raise web.HTTPException(
            reason=f"Version {version} was not found in {_FORMATTERS_MAPPINGS.keys()}"
        )

    formatter_cls: BaseFormatter = _FORMATTERS_MAPPINGS[version]
    return formatter_cls(root_folder=unzipped_root_folder)