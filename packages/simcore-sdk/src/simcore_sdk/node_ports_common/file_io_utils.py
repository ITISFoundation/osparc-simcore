import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import IO, AsyncGenerator, Union

import aiofiles
from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientPayloadError,
    ClientResponse,
    ClientSession,
    web,
)
from models_library.api_schemas_storage import ETag, FileUploadSchema, UploadedPart
from pydantic import AnyUrl
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential
from tqdm import tqdm
from yarl import URL

from . import exceptions
from .constants import CHUNK_SIZE


@dataclass(frozen=True)
class UploadableFileObject:
    file_object: IO
    file_name: str
    file_size: int


async def _file_object_chunk_reader(
    file_object: IO, *, offset: int, total_bytes_to_read: int
) -> AsyncGenerator[bytes, None]:
    await asyncio.get_event_loop().run_in_executor(None, file_object.seek, offset)
    num_read_bytes = 0
    while chunk := await asyncio.get_event_loop().run_in_executor(
        None, file_object.read, min(CHUNK_SIZE, total_bytes_to_read - num_read_bytes)
    ):
        num_read_bytes += len(chunk)
        yield chunk


async def _file_chunk_reader(
    file: Path, *, offset: int, total_bytes_to_read: int
) -> AsyncGenerator[bytes, None]:
    async with aiofiles.open(file, "rb") as f:
        await f.seek(offset)
        num_read_bytes = 0
        while chunk := await f.read(
            min(CHUNK_SIZE, total_bytes_to_read - num_read_bytes)
        ):
            num_read_bytes += len(chunk)
            yield chunk


async def _file_chunk_writer(file: Path, response: ClientResponse, pbar: tqdm):
    async with aiofiles.open(file, "wb") as file_pointer:
        while chunk := await response.content.read(CHUNK_SIZE):
            await file_pointer.write(chunk)
            pbar.update(len(chunk))


log = logging.getLogger(__name__)
_TQDM_FILE_OPTIONS = dict(
    unit="byte",
    unit_scale=True,
    unit_divisor=1024,
    colour="yellow",
    miniters=1,
)


async def download_link_to_file(
    session: ClientSession, url: URL, file_path: Path, *, num_retries: int
):
    log.debug("Downloading from %s to %s", url, file_path)
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(num_retries),
        retry=retry_if_exception_type(ClientConnectionError),
        before_sleep=before_sleep_log(log, logging.WARNING),
    ):
        with attempt:
            async with session.get(url) as response:
                if response.status == 404:
                    raise exceptions.InvalidDownloadLinkError(url)
                if response.status > 299:
                    raise exceptions.TransferError(url)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
                file_size = int(response.headers.get("Content-Length", 0)) or None
                try:
                    with tqdm(
                        desc=f"downloading {url.path} --> {file_path.name}\n",
                        total=file_size,
                        **_TQDM_FILE_OPTIONS,
                    ) as pbar:
                        await _file_chunk_writer(file_path, response, pbar)
                        log.debug("Download complete")
                except ClientPayloadError as exc:
                    raise exceptions.TransferError(url) from exc


async def _upload_file_part(
    session: ClientSession,
    file_to_upload: Union[Path, UploadableFileObject],
    part_index: int,
    file_offset: int,
    file_part_size: int,
    num_parts: int,
    upload_url: AnyUrl,
    pbar: tqdm,
    num_retries: int,
) -> tuple[int, ETag]:
    log.debug(
        "--> uploading %s of %s, [%s]...",
        f"{file_part_size=} bytes",
        f"{file_to_upload=}",
        f"{part_index+1}/{num_parts}",
    )
    file_uploader = _file_chunk_reader(
        file_to_upload,  # type: ignore
        offset=file_offset,
        total_bytes_to_read=file_part_size,
    )
    if isinstance(file_to_upload, UploadableFileObject):
        file_uploader = _file_object_chunk_reader(
            file_to_upload.file_object,
            offset=file_offset,
            total_bytes_to_read=file_part_size,
        )
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(num_retries),
        retry=retry_if_exception_type(ClientConnectionError),
        before_sleep=before_sleep_log(log, logging.WARNING),
    ):
        with attempt:
            response = await session.put(
                upload_url,
                data=file_uploader,
                headers={
                    "Content-Length": f"{file_part_size}",
                },
            )
            response.raise_for_status()
            pbar.update(file_part_size)
            # NOTE: the response from minio does not contain a json body
            assert response.status == web.HTTPOk.status_code  # nosec
            assert response.headers  # nosec
            assert "Etag" in response.headers  # nosec
            received_e_tag = json.loads(response.headers["Etag"])
            log.info(
                "--> completed upload %s of %s, [%s], %s",
                f"{file_part_size=}",
                f"{file_to_upload=}",
                f"{part_index+1}/{num_parts}",
                f"{received_e_tag=}",
            )
            return (part_index, received_e_tag)
    raise exceptions.S3TransferError(
        f"Unexpected error while transferring {file_to_upload} to {upload_url}"
    )


async def upload_file_to_presigned_links(
    session: ClientSession,
    file_upload_links: FileUploadSchema,
    file_to_upload: Union[Path, UploadableFileObject],
    *,
    num_retries: int,
) -> list[UploadedPart]:
    file_size = 0
    file_name = ""
    if isinstance(file_to_upload, Path):
        file_size = file_to_upload.stat().st_size
        file_name = file_to_upload.as_posix()
    else:
        file_size = file_to_upload.file_size
        file_name = file_to_upload.file_name

    log.debug("Uploading from %s to %s", f"{file_name=}", f"{file_upload_links=}")

    file_chunk_size = int(file_upload_links.chunk_size)
    num_urls = len(file_upload_links.urls)
    last_chunk_size = file_size - file_chunk_size * (num_urls - 1)
    upload_tasks = []
    with tqdm(
        desc=f"uploading {file_name}\n", total=file_size, **_TQDM_FILE_OPTIONS
    ) as pbar:
        for index, upload_url in enumerate(file_upload_links.urls):
            this_file_chunk_size = (
                file_chunk_size if (index + 1) < num_urls else last_chunk_size
            )
            upload_tasks.append(
                _upload_file_part(
                    session,
                    file_to_upload,
                    index,
                    index * file_chunk_size,
                    this_file_chunk_size,
                    num_urls,
                    upload_url,
                    pbar,
                    num_retries,
                )
            )
        try:
            results = await logged_gather(
                *upload_tasks,
                log=log,
                # NOTE: when the file object is already created it cannot be duplicated so
                # no concurrency is allowed in that case
                max_concurrency=4 if isinstance(file_to_upload, Path) else 1,
            )
            part_to_etag = [
                UploadedPart(number=index + 1, e_tag=e_tag) for index, e_tag in results
            ]
            log.info(
                "Uploaded %s, received %s",
                f"{file_name=}",
                f"{part_to_etag=}",
            )
            return part_to_etag
        except ClientError as exc:
            raise exceptions.S3TransferError(
                f"Could not upload file {file_name}:{exc}"
            ) from exc
