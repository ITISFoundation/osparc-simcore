import asyncio
import fnmatch
import functools
import logging
import types
import zipfile
from contextlib import AsyncExitStack, contextmanager
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, Final, Iterator

import tqdm
from servicelib.logging_utils import log_catch
from servicelib.progress_bar import ProgressBarData
from tqdm.contrib.logging import logging_redirect_tqdm, tqdm_logging_redirect

from .file_utils import remove_directory
from .pools import non_blocking_process_pool_executor, non_blocking_thread_pool_executor

_MIN: Final[int] = 60  # secs
_MAX_UNARCHIVING_WORKER_COUNT: Final[int] = 2
_CHUNK_SIZE: Final[int] = 1024 * 8

log = logging.getLogger(__name__)


class ArchiveError(Exception):
    """
    Error raised while archiving or unarchiving
    """


def _human_readable_size(size, decimal_places=3):
    human_readable_file_size = float(size)
    unit = "B"
    for t_unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if human_readable_file_size < 1024.0:
            unit = t_unit
            break
        human_readable_file_size /= 1024.0

    return f"{human_readable_file_size:.{decimal_places}f}{unit}"


def _compute_tqdm_miniters(byte_size: int) -> float:
    """ensures tqdm minimal iteration is 1 %"""
    return min(byte_size / 100.0, 1.0)


def _strip_undecodable_in_path(path: Path) -> Path:
    return Path(str(path).encode(errors="replace").decode("utf-8"))


def _iter_files_to_compress(
    dir_path: Path, exclude_patterns: set[str] | None
) -> Iterator[Path]:
    exclude_patterns = exclude_patterns if exclude_patterns else set()
    for path in dir_path.rglob("*"):
        if path.is_file() and not any(
            fnmatch.fnmatch(f"{path}", x) for x in exclude_patterns
        ):
            yield path


def _strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    _to_strip = f"{str(to_strip)}/"
    return Path(str(input_path).replace(_to_strip, ""))


class _FastZipFileReader(zipfile.ZipFile):
    """
    Used to gain a speed boost of several orders of magnitude.

    When opening archives the `_RealGetContents` is called
    generating the list of files contained in the zip archive.
    This is done by the constructor.

    If the archive contains a very large amount, the file scan operation
    can take up to seconds. This was observed with 10000+ files.

    When opening the zip file in the background worker the entire file
    list generation can be skipped because the `zipfile.ZipFile.open`
    is used passing `ZipInfo` object as file to decompress.
    Using a `ZipInfo` object does nto require to have the list of
    files contained in the archive.
    """

    def _RealGetContents(self):
        """method disabled"""


_TQDM_FILE_OPTIONS = dict(
    unit="byte",
    unit_scale=True,
    unit_divisor=1024,
    colour="yellow",
    miniters=1,
)
_TQDM_MULTI_FILES_OPTIONS = _TQDM_FILE_OPTIONS | dict(
    unit="file",
    unit_divisor=1000,
)


def _zipfile_single_file_extract_worker(
    zip_file_path: Path,
    file_in_archive: zipfile.ZipInfo,
    destination_folder: Path,
    is_dir: bool,
) -> Path:
    """Extracts file_in_archive from the archive zip_file_path -> destination_folder/file_in_archive

    Extracts in chunks to avoid memory pressure on zip/unzip
    returns: a path to extracted file or directory
    """
    with _FastZipFileReader(zip_file_path) as zf:
        # assemble destination and ensure it exits
        destination_path = destination_folder / file_in_archive.filename

        if is_dir:
            destination_path.mkdir(parents=True, exist_ok=True)
            return destination_path
        desc = f"decompressing {zip_file_path}:{file_in_archive.filename} -> {destination_path}\n"
        with zf.open(name=file_in_archive) as zip_fp, destination_path.open(
            "wb"
        ) as dest_fp, tqdm_logging_redirect(
            total=file_in_archive.file_size,
            desc=desc,
            **(
                _TQDM_FILE_OPTIONS
                | dict(miniters=_compute_tqdm_miniters(file_in_archive.file_size))
            ),
        ) as pbar:
            while chunk := zip_fp.read(_CHUNK_SIZE):
                dest_fp.write(chunk)
                pbar.update(len(chunk))
            return destination_path


def _ensure_destination_subdirectories_exist(
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


async def unarchive_dir(
    archive_to_extract: Path,
    destination_folder: Path,
    *,
    max_workers: int = _MAX_UNARCHIVING_WORKER_COUNT,
    progress_bar: ProgressBarData | None = None,
    log_cb: Callable[[str], Awaitable[None]] | None = None,
) -> set[Path]:
    """Extracts zipped file archive_to_extract to destination_folder,
    preserving all relative files and folders inside the archive

    Returns a set with all the paths extracted from archive. It includes
    all tree leafs, which might include files or empty folders


    NOTE: ``destination_folder`` is fully deleted after error

    ::raise ArchiveError
    """
    if not progress_bar:
        progress_bar = ProgressBarData(steps=1)
    async with AsyncExitStack() as zip_stack:
        zip_file_handler = zip_stack.enter_context(
            zipfile.ZipFile(  # pylint: disable=consider-using-with
                archive_to_extract,
                mode="r",
            )
        )
        zip_stack.enter_context(logging_redirect_tqdm())
        process_pool = zip_stack.enter_context(
            non_blocking_process_pool_executor(max_workers=max_workers)
        )

        # running in process poll is not ideal for concurrency issues
        # to avoid race conditions all subdirectories where files will be extracted need to exist
        # creating them before the extraction is under way avoids the issue
        # the following avoids race conditions while unzippin in parallel
        _ensure_destination_subdirectories_exist(
            zip_file_handler=zip_file_handler,
            destination_folder=destination_folder,
        )

        futures: list[asyncio.Future] = [
            asyncio.get_event_loop().run_in_executor(
                process_pool,
                # ---------
                _zipfile_single_file_extract_worker,
                archive_to_extract,
                zip_entry,
                destination_folder,
                zip_entry.is_dir(),
            )
            for zip_entry in zip_file_handler.infolist()
        ]

        try:
            extracted_paths: list[Path] = []
            total_file_size = sum(
                zip_entry.file_size for zip_entry in zip_file_handler.infolist()
            )
            async with AsyncExitStack() as progress_stack:
                sub_prog = await progress_stack.enter_async_context(
                    progress_bar.sub_progress(steps=total_file_size)
                )
                tqdm_progress = progress_stack.enter_context(
                    tqdm.tqdm(
                        desc=f"decompressing {archive_to_extract} -> {destination_folder} [{len(futures)} file{'s' if len(futures) > 1 else ''}"
                        f"/{_human_readable_size(archive_to_extract.stat().st_size)}]\n",
                        total=total_file_size,
                        **_TQDM_MULTI_FILES_OPTIONS,
                    )
                )
                for future in asyncio.as_completed(futures):
                    extracted_path = await future
                    extracted_file_size = extracted_path.stat().st_size
                    if tqdm_progress.update(extracted_file_size) and log_cb:
                        with log_catch(log, reraise=False):
                            await log_cb(f"{tqdm_progress}")
                    await sub_prog.update(extracted_file_size)
                    extracted_paths.append(extracted_path)

        except Exception as err:
            for f in futures:
                f.cancel()

            # wait until all tasks are cancelled
            await asyncio.wait(
                futures, timeout=2 * _MIN, return_when=asyncio.ALL_COMPLETED
            )

            # now we can cleanup
            if destination_folder.exists() and destination_folder.is_dir():
                await remove_directory(destination_folder, ignore_errors=True)

            raise ArchiveError(
                f"Failed unarchiving {archive_to_extract} -> {destination_folder} due to {type(err)}."
                f"Details: {err}"
            ) from err

        # NOTE: extracted_paths includes all tree leafs, which might include files and empty folders
        return {
            p
            for p in extracted_paths
            if p.is_file() or (p.is_dir() and not any(p.glob("*")))
        }


@contextmanager
def _progress_enabled_zip_write_handler(
    zip_file_handler: zipfile.ZipFile, progress_bar: tqdm.tqdm
) -> Iterator[zipfile.ZipFile]:
    """This function overrides the default zip write fct to allow to get progress using tqdm library"""

    def _write_with_progress(
        original_write_fct, self, data, pbar  # pylint: disable=unused-argument
    ):
        pbar.update(len(data))
        return original_write_fct(data)

    # Replace original write() with a wrapper to track progress
    assert zip_file_handler.fp  # nosec
    old_write_method = zip_file_handler.fp.write
    zip_file_handler.fp.write = types.MethodType(  # type: ignore[assignment]
        partial(_write_with_progress, old_write_method, pbar=progress_bar),
        zip_file_handler.fp,
    )
    try:
        yield zip_file_handler
    finally:
        zip_file_handler.fp.write = old_write_method  # type: ignore[method-assign]


def _add_to_archive(
    dir_to_compress: Path,
    destination: Path,
    compress: bool,
    store_relative_path: bool,
    update_progress,
    loop,
    exclude_patterns: set[str] | None = None,
) -> None:
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    folder_size_bytes = sum(
        file.stat().st_size
        for file in _iter_files_to_compress(dir_to_compress, exclude_patterns)
    )
    desc = f"compressing {dir_to_compress} -> {destination}"
    with tqdm_logging_redirect(
        desc=f"{desc}\n",
        total=folder_size_bytes,
        **(
            _TQDM_FILE_OPTIONS
            | dict(miniters=_compute_tqdm_miniters(folder_size_bytes))
        ),
    ) as progress_bar, _progress_enabled_zip_write_handler(
        zipfile.ZipFile(destination, "w", compression=compression), progress_bar
    ) as zip_file_handler:
        for file_to_add in _iter_files_to_compress(dir_to_compress, exclude_patterns):
            progress_bar.set_description(f"{desc}/{file_to_add.name}\n")
            file_name_in_archive = (
                _strip_directory_from_path(file_to_add, dir_to_compress)
                if store_relative_path
                else file_to_add
            )

            # because surrogates are not allowed in zip files,
            # replacing them will ensure errors will not happen.
            escaped_file_name_in_archive = _strip_undecodable_in_path(
                file_name_in_archive
            )

            zip_file_handler.write(file_to_add, escaped_file_name_in_archive)
            asyncio.run_coroutine_threadsafe(
                update_progress(file_to_add.stat().st_size), loop
            )


async def _update_progress(prog: ProgressBarData, delta: float) -> None:
    await prog.update(delta)


async def archive_dir(
    dir_to_compress: Path,
    destination: Path,
    *,
    compress: bool,
    store_relative_path: bool,
    exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData | None = None,
) -> None:
    """
    When archiving, undecodable bytes in filenames will be escaped,
    zipfile does not like them.
    When unarchiveing, the **escaped version** of the file names
    will be created.

    The **exclude_patterns** is a set of patterns created using
    Unix shell-style wildcards to exclude files and directories.

    destination: Path deleted if errors

    ::raise ArchiveError
    """
    if not progress_bar:
        progress_bar = ProgressBarData(steps=1)

    async with AsyncExitStack() as stack:

        folder_size_bytes = sum(
            file.stat().st_size
            for file in _iter_files_to_compress(dir_to_compress, exclude_patterns)
        )
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(folder_size_bytes)
        )
        thread_pool = stack.enter_context(
            non_blocking_thread_pool_executor(max_workers=1)
        )
        try:
            await asyncio.get_event_loop().run_in_executor(
                thread_pool,
                # ---------
                _add_to_archive,
                dir_to_compress,
                destination,
                compress,
                store_relative_path,
                functools.partial(_update_progress, sub_progress),
                asyncio.get_event_loop(),
                exclude_patterns,
            )
        except Exception as err:
            if destination.is_file():
                destination.unlink(missing_ok=True)

            raise ArchiveError(
                f"Failed archiving {dir_to_compress} -> {destination} due to {type(err)}."
                f"Details: {err}"
            ) from err

        except BaseException:
            if destination.is_file():
                destination.unlink(missing_ok=True)
            raise


def is_leaf_path(p: Path) -> bool:
    """Tests whether a path corresponds to a file or empty folder, i.e.
    some leaf item in a file-system tree structure
    """
    return p.is_file() or (p.is_dir() and not any(p.glob("*")))


class PrunableFolder:
    """
    Use in conjunction with unarchive on the dest_dir to achieve
    an update of a folder content without deleting updated files

    folder = PrunableFolder(target_dir)

    unarchived = await archive_dir(destination=target_dir, ... )

    folder.prune(exclude=unarchived)

    """

    def __init__(self, folder: Path):
        self.basedir = folder
        self.before_relpaths: set = set()
        self.capture()

    def capture(self) -> None:
        # captures leaf paths in folder at this moment
        self.before_relpaths = {
            p.relative_to(self.basedir)
            for p in self.basedir.rglob("*")
            if is_leaf_path(p)
        }

    def prune(self, exclude: set[Path]) -> None:
        """
        Deletes all paths in folder skipping the exclude set
        """
        assert all(self.basedir in p.parents for p in exclude)  # nosec

        after_relpaths = {p.relative_to(self.basedir) for p in exclude}
        to_delete = self.before_relpaths.difference(after_relpaths)

        for p in to_delete:
            path = self.basedir / p
            assert path.exists()  # nosec

            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    # prevents deleting non-empty folders
                    pass

        # second pass to delete empty folders
        # after deleting files, some folders might have been left empty
        for p in self.basedir.rglob("*"):
            if p.is_dir() and p not in exclude and not any(p.glob("*")):
                p.rmdir()


__all__ = (
    "archive_dir",
    "ArchiveError",
    "is_leaf_path",
    "PrunableFolder",
    "unarchive_dir",
)
