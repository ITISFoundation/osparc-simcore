import logging
from pathlib import Path
from typing import Tuple

from passlib import pwd
from servicelib.archiving_utils import archive_dir, unarchive_dir

from .async_hashing import Algorithm, checksum
from .exceptions import ExporterException
from .utils import rename

log = logging.getLogger(__name__)


def _get_random_chars(length: int) -> str:
    return pwd.genword(entropy=52, charset="hex")[:length]


def _get_osparc_export_name(sha256_sum: str, algorithm: Algorithm) -> str:
    return f"{_get_random_chars(4)}#{algorithm.name}={sha256_sum}.osparc"


def validate_osparc_import_name(file_name: str) -> Tuple[Algorithm, str]:
    """returns: sha256 from file signature if present or raises an error"""
    # sample: 0a3a#SHA256=02d03b65911aae7662a8fa5fa4847d0b8f722a022d95b37b4a02960ff736853a.osparc
    if not file_name.endswith(".osparc"):
        raise ExporterException(
            f"Provided file name must haave .osparc extension file_name={file_name}"
        )

    parts = file_name.replace(".osparc", "").split("#")
    if len(parts) != 2:
        raise ExporterException(
            f"Could not find a digest in provided file_name={file_name}"
        )
    digest = parts[1]

    digest_parts = digest.split("=")
    if len(digest_parts) != 2:
        raise ExporterException(
            f"Could not find a valid digest in provided file_name={file_name}"
        )
    algorithm, digest_sum = Algorithm[digest_parts[0]], digest_parts[1]
    return algorithm, digest_sum


def search_for_unzipped_path(search_path: Path) -> Path:
    found_dirs = []
    for path in search_path.iterdir():
        if path.is_dir():
            found_dirs.append(path)

    if len(found_dirs) != 1:
        raise ExporterException(
            f"Unexpected number of directories after unzipping {[str(x) for x in found_dirs]}"
        )
    return search_path / found_dirs[0]


async def zip_folder(folder_to_zip: Path, destination_folder: Path) -> Path:
    """Zips a folder and returns the path to the new archive"""

    archived_file = destination_folder / "archive.zip"
    if archived_file.is_file():
        raise ExporterException(
            f"Cannot archive '{folder_to_zip}' because '{str(archived_file)}' already exists"
        )

    await archive_dir(
        dir_to_compress=folder_to_zip,
        destination=archived_file,
        compress=True,
        store_relative_path=True,
    )

    # compute checksum and rename
    sha256_sum = await checksum(file_path=archived_file, algorithm=Algorithm.SHA256)

    # opsarc_formatted_name= "4_rand_chars#sha256_sum.osparc"
    osparc_formatted_name = Path(folder_to_zip) / _get_osparc_export_name(
        sha256_sum=sha256_sum, algorithm=Algorithm.SHA256
    )
    await rename(archived_file, osparc_formatted_name)

    return osparc_formatted_name


async def unzip_folder(archive_to_extract: Path, destination_folder: Path) -> Path:
    try:
        await unarchive_dir(
            archive_to_extract=archive_to_extract, destination_folder=destination_folder
        )
    except Exception as e:
        files_in_destination = [str(x) for x in destination_folder.rglob("*")]
        message = (
            f"There was an error while extracting '{archive_to_extract}' directory to "
            f"'{destination_folder}'; files_in_destination_directory={files_in_destination}"
        )
        log.exception(message)
        raise ExporterException(message) from e

    return search_for_unzipped_path(destination_folder)
