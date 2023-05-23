from pathlib import Path

from servicelib.archiving_utils import archive_dir

from .exceptions import ExporterException


async def zip_folder(
    folder_to_zip: Path, destination_folder: Path, project_id: str
) -> Path:
    """Zips a folder and returns the path to the new archive"""

    archive_name: Path = destination_folder / f"sds_{project_id}.zip"
    if archive_name.is_file():
        raise ExporterException(
            f"Cannot archive '{folder_to_zip}' because '{archive_name}' already exists"
        )

    await archive_dir(
        dir_to_compress=folder_to_zip,
        destination=archive_name,
        compress=True,
        store_relative_path=True,
    )

    return archive_name
