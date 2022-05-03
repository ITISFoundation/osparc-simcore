from pathlib import Path
from typing import Dict

from ..exceptions import ExporterException
from .base_formatter import BaseFormatter
from .formatter_v1 import FormatterV1
from .formatter_v2 import FormatterV2
from .models import ManifestFile

# maps manifest version to available formatters
_FORMATTERS_MAPPINGS: Dict[str, BaseFormatter] = {"1": FormatterV1, "2": FormatterV2}


async def validate_manifest(unzipped_root_folder: Path) -> BaseFormatter:
    """
    Checks if the file contains a manifest and will return the
    formatter specified in the manifest's version
    """

    manifest_from_file = await ManifestFile.model_from_file(
        root_dir=unzipped_root_folder
    )

    if manifest_from_file.version not in _FORMATTERS_MAPPINGS:
        raise ExporterException(
            (
                f"Version {manifest_from_file.version} is not supported by this deployment. "
                "The project you are trying to import might be exported in a newer version, "
                "or this deployment is using an older version."
            )
        )

    formatter_cls: BaseFormatter = _FORMATTERS_MAPPINGS[manifest_from_file.version]
    return formatter_cls(root_folder=unzipped_root_folder)
