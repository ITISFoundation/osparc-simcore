import asyncio
import logging
import zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Iterator


log = logging.getLogger(__name__)


def _full_file_path_from_dir_and_subdirs(dir_path: Path) -> Iterator[Path]:
    for path in dir_path.rglob("*"):
        if path.is_file():
            yield path


def _strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    to_strip = f"{str(to_strip)}/"
    return Path(str(input_path).replace(to_strip, ""))


def _read_in_chunks(file_object, chunk_size=1024 * 8):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 8k."""
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data


def _zipfile_single_file_extract_worker(
    zip_file_path: Path, file_in_archive: str, destination_folder: Path
) -> None:
    """Extracing in chunks to avoid memory pressure on zip/unzip"""
    with zipfile.ZipFile(zip_file_path) as zf:
        # assemble destination and ensure it exits
        destination_path = destination_folder / file_in_archive

        with zf.open(name=file_in_archive) as zip_fp:
            with open(destination_path, "wb") as destination_fp:
                for chunk in _read_in_chunks(zip_fp):
                    destination_fp.write(chunk)


def ensure_destination_subdirectories_exist(
    zip_file_handler: zipfile.ZipFile, destination_folder: Path
) -> None:
    # assemble full destination paths
    full_destination_paths = {
        destination_folder / entry.filename for entry in zip_file_handler.infolist()
    }
    # extract all possible subdirectories
    subdirectories = {x.parent for x in full_destination_paths}
    # create all subdirectories before extracting
    for subdirectory in subdirectories:
        Path(subdirectory).mkdir(parents=True, exist_ok=True)


async def unarchive_dir(archive_to_extract: Path, destination_folder: Path) -> None:
    with zipfile.ZipFile(archive_to_extract, mode="r") as zip_file_handler:
        with ProcessPoolExecutor() as pool:
            loop = asyncio.get_event_loop()

            # running in process poll is not ideal for concurrency issues
            # to avoid race conditions all subdirectories where files will be extracted need to exist
            # creating them before the extraction is under way avoids the issue
            # the following avoids race conditions while unzippin in parallel
            ensure_destination_subdirectories_exist(
                zip_file_handler=zip_file_handler,
                destination_folder=destination_folder,
            )

            tasks = [
                loop.run_in_executor(
                    pool,
                    _zipfile_single_file_extract_worker,
                    archive_to_extract,
                    zip_entry.filename,
                    destination_folder,
                )
                for zip_entry in zip_file_handler.infolist()
                if zip_entry.is_file()
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


__all__ = ["archive_dir", "unarchive_dir"]