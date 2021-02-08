import asyncio
import logging
import zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple, Iterator

from passlib import pwd

from .async_hashing import Algorithm, checksum
from .exceptions import ExporterException
from .utils import rename

log = logging.getLogger(__name__)


def _full_file_path_from_dir_and_subdirs(dir_path: Path) -> Iterator[Path]:
    """returns a generator"""
    for path in dir_path.rglob("*"):
        if path.is_file():
            yield path


def _strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    to_strip = f"{str(to_strip)}/"
    return Path(str(input_path).replace(to_strip, ""))


def _parallel_zipfile_extract_worker(
    zip_file_path: Path, file_in_archive: str, destination_folder: Path
) -> None:
    with open(zip_file_path, "rb") as f:
        zf = zipfile.ZipFile(f)
        zf.extract(file_in_archive, destination_folder)


async def unarchive_dir(archive_to_extract: Path, destination_folder: Path) -> None:
    with open(archive_to_extract, "rb") as file_handler:
        zip_file_handler = zipfile.ZipFile(file_handler)
        with ProcessPoolExecutor() as pool:
            loop = asyncio.get_event_loop()

            tasks = [
                loop.run_in_executor(
                    pool,
                    _parallel_zipfile_extract_worker,
                    archive_to_extract,
                    zip_entry.filename,
                    destination_folder,
                )
                for zip_entry in zip_file_handler.infolist()
            ]

            await asyncio.gather(*tasks)


def _serial_add_to_archive(
    dir_to_compress: Path, destination: Path, compress: bool, store_relative_path: bool
) -> None:
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(destination, "w", compression=compression) as zip_file_handler:
        files_to_compress_generator = _full_file_path_from_dir_and_subdirs(
            dir_to_compress
        )
        for file_to_add in files_to_compress_generator:
            try:
                file_name_in_archive = (
                    _strip_directory_from_path(file_to_add, dir_to_compress)
                    if store_relative_path
                    else file_to_add
                )
                zip_file_handler.write(file_to_add, file_name_in_archive)
            except ValueError:
                log.exception("Could write files to archive, please check logs")
                return False
    return True


async def archive_dir(
    dir_to_compress: Path, destination: Path, compress: bool, store_relative_path: bool
) -> bool:
    with ProcessPoolExecutor(max_workers=1) as pool:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            _serial_add_to_archive,
            dir_to_compress,
            destination,
            compress,
            store_relative_path,
        )


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


async def zip_folder(input_path: Path) -> Path:
    """Zips a folder and returns the path to the new archive"""
    zip_file = Path(input_path.parent.parent) / "archive.zip"
    if zip_file.is_file():
        raise ExporterException(
            f"Cannot archive because file already exists '{str(zip_file)}'"
        )

    await archive_dir(
        dir_to_compress=input_path.parent,
        destination=zip_file,
        compress=True,
        store_relative_path=True,
    )

    # compute checksum and rename
    sha256_sum = await checksum(file_path=zip_file, algorithm=Algorithm.SHA256)

    # opsarc_formatted_name= "4_rand_chars#sha256_sum.osparc"
    osparc_formatted_name = Path(input_path.parent) / _get_osparc_export_name(
        sha256_sum=sha256_sum, algorithm=Algorithm.SHA256
    )
    await rename(zip_file, osparc_formatted_name)

    return osparc_formatted_name


async def unzip_folder(input_path: Path) -> Path:
    log.info("unzip %s to %s", input_path, input_path.parent)
    await unarchive_dir(
        archive_to_extract=input_path, destination_folder=input_path.parent
    )
    return search_for_unzipped_path(input_path.parent)
