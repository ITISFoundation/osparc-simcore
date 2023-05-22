import logging
from pathlib import Path

from passlib import pwd
from servicelib.archiving_utils import archive_dir

from .async_hashing import Algorithm, checksum
from .exceptions import ExporterException
from .utils import rename

log = logging.getLogger(__name__)


def _get_random_chars(length: int) -> str:
    return pwd.genword(entropy=52, charset="hex")[:length]


def _get_osparc_export_name(sha256_sum: str, algorithm: Algorithm) -> str:
    return f"{_get_random_chars(4)}#{algorithm.name}={sha256_sum}.osparc"


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
