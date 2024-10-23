import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Coroutine
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Final, Protocol, runtime_checkable

import aiofiles
from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientPayloadError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    RequestInfo,
)
from aiohttp.typedefs import LooseHeaders
from models_library.api_schemas_storage import ETag, FileUploadSchema, UploadedPart
from models_library.basic_types import IDStr, SHA256Str
from pydantic import AnyUrl, NonNegativeInt
from servicelib.aiohttp import status
from servicelib.logging_utils import log_catch
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather, partition_gen
from tenacity.after import after_log
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception, retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential
from tqdm import tqdm
from tqdm.contrib.logging import tqdm_logging_redirect
from yarl import URL

from . import exceptions
from .constants import CHUNK_SIZE

_logger = logging.getLogger(__name__)

_CONCURRENT_MULTIPART_UPLOADS_COUNT: Final[NonNegativeInt] = 10
_VALID_HTTP_STATUS_CODES: Final[NonNegativeInt] = 299


@dataclass(frozen=True)
class UploadableFileObject:
    file_object: IO
    file_name: str
    file_size: int
    sha256_checksum: SHA256Str | None = None


class _ExtendedClientResponseError(ClientResponseError):
    def __init__(
        self,
        request_info: RequestInfo,
        history: tuple[ClientResponse, ...],
        body: str,
        *,
        code: int | None = None,
        status_code: int | None = None,
        message: str = "",
        headers: LooseHeaders | None = None,
    ):
        super().__init__(
            request_info,
            history,
            code=code,
            status=status_code,
            message=message,
            headers=headers,
        )
        self.body = body

    def __str__(self) -> str:
        # When dealing with errors coming from S3 it is hard to conclude
        # what is wrong from a generic `400 Bad Request` extending
        # stacktrace with body. SEE links below for details:
        # - https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html
        # - https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingRESTError.html
        return (
            f"status={self.status}, "
            f"message={self.message}, "
            f"url={self.request_info.real_url}, "
            f"body={self.body}"
        )


async def _raise_for_status(response: ClientResponse) -> None:
    if response.status >= status.HTTP_400_BAD_REQUEST:
        body = await response.text()
        raise _ExtendedClientResponseError(
            response.request_info,
            response.history,
            body,
            status_code=response.status,
            message=response.reason or "",
            headers=response.headers,
        )


def _compute_tqdm_miniters(byte_size: int) -> float:
    """ensures tqdm minimal iteration is 1.5 %"""
    return min(1.5 * byte_size / 100.0, 1.0)


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


@dataclass(frozen=True)
class ProgressData:
    current: int
    total: int


@runtime_checkable
class LogRedirectCB(Protocol):
    async def __call__(self, log: str) -> None:
        ...


async def _file_chunk_writer(
    file: Path,
    response: ClientResponse,
    pbar: tqdm,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
):
    async with aiofiles.open(file, "wb") as file_pointer:
        while chunk := await response.content.read(CHUNK_SIZE):
            await file_pointer.write(chunk)
            if io_log_redirect_cb and pbar.update(len(chunk)):
                with log_catch(_logger, reraise=False):
                    await io_log_redirect_cb(f"{pbar}")
            await progress_bar.update(len(chunk))


_TQDM_FILE_OPTIONS: dict[str, Any] = {
    "unit": "byte",
    "unit_scale": True,
    "unit_divisor": 1024,
    "colour": "yellow",
    "miniters": 1,
}


async def download_link_to_file(
    session: ClientSession,
    url: URL,
    file_path: Path,
    *,
    num_retries: int,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
):
    _logger.debug("Downloading from %s to %s", url, file_path)
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(num_retries),
        retry=retry_if_exception_type(ClientConnectionError),
        before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
        after=after_log(_logger, log_level=logging.ERROR),
    ):
        with attempt:
            async with AsyncExitStack() as stack:
                response = await stack.enter_async_context(session.get(url))
                if response.status == status.HTTP_404_NOT_FOUND:
                    raise exceptions.InvalidDownloadLinkError(url)
                if response.status > _VALID_HTTP_STATUS_CODES:
                    raise exceptions.TransferError(url)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
                file_size = int(response.headers.get("Content-Length", 0)) or None
                try:
                    tqdm_progress = stack.enter_context(
                        tqdm_logging_redirect(
                            desc=f"downloading {url.path} --> {file_path.name}\n",
                            total=file_size,
                            **(
                                _TQDM_FILE_OPTIONS
                                | {
                                    "miniters": (
                                        _compute_tqdm_miniters(file_size)
                                        if file_size
                                        else 1
                                    )
                                }
                            ),
                        )
                    )
                    sub_progress = await stack.enter_async_context(
                        progress_bar.sub_progress(
                            steps=file_size or 1,
                            description=IDStr(f"downloading {file_path.name}"),
                        )
                    )

                    await _file_chunk_writer(
                        file_path,
                        response,
                        tqdm_progress,
                        io_log_redirect_cb,
                        sub_progress,
                    )
                    _logger.debug("Download complete")
                except ClientPayloadError as exc:
                    raise exceptions.TransferError(url) from exc


def _check_for_aws_http_errors(exc: BaseException) -> bool:
    """returns: True if it should retry when http exception is detected"""

    if not isinstance(exc, _ExtendedClientResponseError):
        return False

    # Sometimes AWS responds with a 500 or 503 which shall be retried,
    # form more information see:
    # https://aws.amazon.com/premiumsupport/knowledge-center/http-5xx-errors-s3/
    if exc.status in (
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    ):
        return True

    return False


async def _session_put(
    session: ClientSession,
    file_part_size: int,
    upload_url: str,
    pbar: tqdm,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
    file_uploader: Any | None,
) -> str:
    async with session.put(
        upload_url, data=file_uploader, headers={"Content-Length": f"{file_part_size}"}
    ) as response:
        await _raise_for_status(response)
        if io_log_redirect_cb and pbar.update(file_part_size):
            with log_catch(_logger, reraise=False):
                await io_log_redirect_cb(f"{pbar}")
        await progress_bar.update(file_part_size)

        # NOTE: the response from minio does not contain a json body
        assert response.status == status.HTTP_200_OK  # nosec
        assert response.headers  # nosec
        assert "Etag" in response.headers  # nosec
        etag: str = json.loads(response.headers["Etag"])
        return etag


async def _upload_file_part(
    session: ClientSession,
    file_to_upload: Path | UploadableFileObject,
    part_index: int,
    file_offset: int,
    file_part_size: int,
    upload_url: AnyUrl,
    pbar: tqdm,
    num_retries: int,
    *,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
) -> tuple[int, ETag]:
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
        retry=retry_if_exception_type(ClientConnectionError)
        | retry_if_exception(_check_for_aws_http_errors),
        before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
        after=after_log(_logger, log_level=logging.ERROR),
    ):
        with attempt:
            received_e_tag = await _session_put(
                session=session,
                file_part_size=file_part_size,
                upload_url=str(upload_url),
                pbar=pbar,
                io_log_redirect_cb=io_log_redirect_cb,
                progress_bar=progress_bar,
                file_uploader=file_uploader,
            )
            return (part_index, received_e_tag)
    msg = f"Unexpected error while transferring {file_to_upload} to {upload_url}"
    raise exceptions.S3TransferError(msg)


def _get_file_size_and_name(
    file_to_upload: Path | UploadableFileObject,
) -> tuple[int, str]:
    if isinstance(file_to_upload, Path):
        file_size = file_to_upload.stat().st_size
        file_name = file_to_upload.as_posix()
    else:
        file_size = file_to_upload.file_size
        file_name = file_to_upload.file_name

    return file_size, file_name


async def _process_batch(
    *,
    upload_tasks: list[Coroutine],
    max_concurrency: int,
    file_name: str,
    file_size: int,
    file_chunk_size: int,
    last_chunk_size: int,
) -> list[UploadedPart]:
    results: list[UploadedPart] = []
    try:
        upload_results = await logged_gather(
            *upload_tasks, log=_logger, max_concurrency=max_concurrency
        )

        for i, e_tag in upload_results:
            results.append(UploadedPart(number=i + 1, e_tag=e_tag))
    except _ExtendedClientResponseError as e:
        if e.status == status.HTTP_400_BAD_REQUEST and "RequestTimeout" in e.body:
            raise exceptions.AwsS3BadRequestRequestTimeoutError(e.body) from e
    except ClientError as exc:
        msg = (
            f"Could not upload file {file_name} ({file_size=}, "
            f"{file_chunk_size=}, {last_chunk_size=}):{exc}"
        )
        raise exceptions.S3TransferError(msg) from exc

    return results


async def upload_file_to_presigned_links(
    session: ClientSession,
    file_upload_links: FileUploadSchema,
    file_to_upload: Path | UploadableFileObject,
    *,
    num_retries: int,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
) -> list[UploadedPart]:
    file_size, file_name = _get_file_size_and_name(file_to_upload)

    # NOTE: when the file object is already created it cannot be duplicated so
    # no concurrency is allowed in that case
    max_concurrency: int = 4 if isinstance(file_to_upload, Path) else 1

    file_chunk_size = int(file_upload_links.chunk_size)
    num_urls: int = len(file_upload_links.urls)
    last_chunk_size: int = file_size - file_chunk_size * (num_urls - 1)

    results: list[UploadedPart] = []
    async with AsyncExitStack() as stack:
        tqdm_progress = stack.enter_context(
            tqdm_logging_redirect(
                desc=f"uploading {file_name}\n",
                total=file_size,
                **(
                    _TQDM_FILE_OPTIONS | {"miniters": _compute_tqdm_miniters(file_size)}
                ),
            )
        )
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(
                steps=file_size, description=IDStr(f"uploading {file_name}")
            )
        )

        indexed_urls: list[tuple[int, AnyUrl]] = list(enumerate(file_upload_links.urls))
        for partition_of_indexed_urls in partition_gen(
            indexed_urls, slice_size=_CONCURRENT_MULTIPART_UPLOADS_COUNT
        ):
            upload_tasks: list[Coroutine] = []
            for index, upload_url in partition_of_indexed_urls:
                this_file_chunk_size = (
                    file_chunk_size if (index + 1) < num_urls else last_chunk_size
                )
                upload_tasks.append(
                    _upload_file_part(
                        session=session,
                        file_to_upload=file_to_upload,
                        part_index=index,
                        file_offset=index * file_chunk_size,
                        file_part_size=this_file_chunk_size,
                        upload_url=upload_url,
                        pbar=tqdm_progress,
                        num_retries=num_retries,
                        io_log_redirect_cb=io_log_redirect_cb,
                        progress_bar=sub_progress,
                    )
                )
            results.extend(
                await _process_batch(
                    upload_tasks=upload_tasks,
                    max_concurrency=max_concurrency,
                    file_name=file_name,
                    file_size=file_chunk_size,
                    file_chunk_size=file_chunk_size,
                    last_chunk_size=last_chunk_size,
                )
            )

    return results
